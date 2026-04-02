"""Decomposed single-phase runner for the TDD dev-cycle.

Runs one phase of one step — used by the /dev-cycle Claude Code skill
for interactive, decomposed execution.

Usage:
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --step 3 --phase red
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --step 3 --phase green --context "previous failures..."
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --phase final-review

Exit code 0 = success, 1 = failure.
Structured JSON to stdout, human-readable progress to stderr.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from config import PipelineConfig
from plan_parser import parse_plan
from state_machine import Phase
from steps import (
    run_final_review,
    run_green,
    run_green_fix,
    run_lint,
    run_red,
    run_verify,
)

logger = logging.getLogger(__name__)

PHASES = ("red", "green", "verify", "lint", "commit", "final-review")


def _resolve_plan_path(plan_path: str, cwd: str) -> str:
    """Resolve plan_path relative to the repo root.

    Args:
        plan_path: Plan path as provided by the user (may be relative).
        cwd: Repository root directory.

    Returns:
        Absolute path string to the plan file.
    """
    p = Path(plan_path)
    if not p.is_absolute():
        p = Path(cwd).resolve() / p
    return str(p.resolve())


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for single-phase execution.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Run a single phase of one pipeline step.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Write failing tests for step 3
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --step 3 --phase red

  # Implement step 3
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --step 3 --phase green

  # Run tests for step 3
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --step 3 --phase verify

  # Run final review on full branch diff
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --phase final-review
""",
    )
    parser.add_argument(
        "--plan",
        required=True,
        help="Path to the plan markdown file (relative to repo root).",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="Step number to operate on (required for all phases except final-review).",
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=PHASES,
        help="Which phase to run.",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Extra context for the agent (e.g. previous failure output).",
    )
    return parser


async def _run_phase(args: argparse.Namespace, config: PipelineConfig) -> dict:
    """Execute a single phase and return a result dict.

    Args:
        args: Parsed CLI arguments with phase, step, and context.
        config: Pipeline configuration.

    Returns:
        Dict with phase results suitable for JSON serialization.
    """
    plan = parse_plan(Path(config.plan_path))
    phase = args.phase
    step_num = args.step
    context = args.context

    # final-review doesn't need a step
    if phase == "final-review":
        logger.info("[FINAL_REVIEW] Running static checks + /review")
        result = run_final_review(config)
        return {
            "phase": "final-review",
            "verdict": result.verdict,
            "summary": result.summary,
            "findings": result.findings,
        }

    # All other phases require a step number
    if step_num is None:
        logger.error("--step is required for phase '%s'", phase)
        return {"error": f"--step is required for phase '{phase}'"}

    # Find the step in the plan
    step = next((s for s in plan.steps if s.number == step_num), None)
    if step is None:
        logger.error("Step %d not found in plan", step_num)
        return {"error": f"Step {step_num} not found in plan"}

    # Files from prior steps
    prior_files = []
    for s in plan.steps:
        if s.number < step_num:
            prior_files.extend(s.files)

    if phase == "red":
        logger.info("[RED] Step %d — writing tests", step_num)
        red_result = await run_red(
            step=step,
            plan_text=plan.raw_text,
            config=config,
            prior_files=prior_files,
        )
        return {
            "phase": "red",
            "step": step_num,
            "test_files": red_result.test_files,
            "cost_usd": red_result.cost_usd,
        }

    elif phase == "green":
        logger.info("[GREEN] Step %d — implementing", step_num)
        test_files = [f for f in step.files if "test" in f.lower()]
        green_result = await run_green(
            step=step,
            plan_text=plan.raw_text,
            test_files=test_files,
            config=config,
            prior_files=prior_files,
            extra_context=context,
        )
        return {
            "phase": "green",
            "step": step_num,
            "changed_files": green_result.changed_files,
            "cost_usd": green_result.cost_usd,
        }

    elif phase == "verify":
        logger.info("[VERIFY] Step %d — running tests", step_num)
        test_dir = _find_test_dir(step.files, config.cwd)
        verify_result = run_verify(test_dir=test_dir, config=config)
        return {
            "phase": "verify",
            "step": step_num,
            "passed": verify_result.passed,
            "num_tests": verify_result.num_tests,
            "num_failures": verify_result.num_failures,
            "failures": verify_result.failures,
        }

    elif phase == "lint":
        logger.info("[LINT] Step %d — format & lint", step_num)
        lint_result = run_lint(changed_files=step.files, config=config)
        return {
            "phase": "lint",
            "step": step_num,
            "passed": lint_result.passed,
            "violations": lint_result.violations,
        }

    elif phase == "commit":
        logger.info("[COMMIT] Step %d", step_num)
        subprocess.run(
            ["git", "add", "-A"],
            cwd=config.cwd,
            capture_output=True,
            text=True,
        )
        commit_msg = f"Step {step_num}: {step.title}"
        commit_proc = subprocess.run(
            ["git", "commit", "-m", commit_msg, "--allow-empty"],
            cwd=config.cwd,
            capture_output=True,
            text=True,
        )
        committed = commit_proc.returncode == 0
        return {
            "phase": "commit",
            "step": step_num,
            "committed": committed,
            "message": commit_msg,
        }

    return {"error": f"Unknown phase: {phase}"}


def _find_test_dir(files: list[str], cwd: str) -> str:
    """Find the project directory for pytest based on step files.

    Args:
        files: Step file paths.
        cwd: Repository root.

    Returns:
        Directory path for uv run --directory.
    """
    for f in files:
        full = Path(cwd) / f
        current = full.parent
        while current != Path(cwd).parent:
            if (current / "pyproject.toml").exists():
                return str(current)
            current = current.parent
    return cwd


def main() -> int:
    """CLI entry point for single-phase execution.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    parser = _build_parser()
    args = parser.parse_args()

    cwd = str(Path(__file__).resolve().parent.parent.parent)
    plan_path = _resolve_plan_path(args.plan, cwd)

    config = PipelineConfig(
        plan_path=plan_path,
        step=args.step,
        cwd=cwd,
    )

    try:
        result = asyncio.run(_run_phase(args, config))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        result = {"error": "Interrupted by user (KeyboardInterrupt)."}

    json.dump(result, sys.stdout, indent=2, default=str)
    print(file=sys.stdout)

    is_error = "error" in result
    is_failure = result.get("passed") is False
    return 1 if (is_error or is_failure) else 0


if __name__ == "__main__":
    sys.exit(main())

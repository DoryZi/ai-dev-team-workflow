"""Decomposed single-phase runner for the dev-cycle.

Runs one phase of one step — used by the /dev-cycle Claude Code skill
for interactive, decomposed execution.

Usage:
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --step 3 --phase implement
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --step 3 --phase verify
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --phase explore
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --step 3 --phase review --review-mode agent
    uv run --directory agent_tools/dev_cycle python run_step.py \
        --plan plans/foo.md --phase eng-review --review-mode agent
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

from steps import (
    run_eng_review,
    run_explore,
    run_final_review,
    run_implement,
    run_review,
    run_verify,
)
from vault import load_context_for_step, plan_slug, RunManifest

logger = logging.getLogger(__name__)

PHASES = ("explore", "implement", "verify", "review", "commit", "eng-review", "final-review")


def _detect_repo_root() -> str:
    """Auto-detect the repository root via git.

    Returns:
        Absolute path to the repo root.

    Raises:
        RuntimeError: If git rev-parse fails.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to detect repo root via git: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


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
  # Explore the codebase (plan-wide, no --step needed)
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --phase explore

  # Implement step 3 (writes code + tests)
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --step 3 --phase implement

  # Verify step 3 (lint + pytest)
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --step 3 --phase verify

  # LLM convention review for step 3
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --step 3 --phase review --review-mode agent

  # Engineering review on full branch diff
  uv run --directory agent_tools/dev_cycle python run_step.py \\
      --plan plans/foo.md --phase eng-review --review-mode agent

  # Final review (static + /review CLI)
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
        help="Step number to operate on (required for per-step phases).",
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
    parser.add_argument(
        "--review-mode",
        choices=["static", "agent", "full"],
        default="static",
        help="Review depth for review/eng-review/final-review phases.",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Repository root directory (default: auto-detect via git).",
    )
    parser.add_argument(
        "--vault-run",
        default=None,
        help="Vault run ID (timestamp) to load context from. Enables vault context injection.",
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

    # --- Plan-wide phases (no --step needed) ---

    if phase == "explore":
        logger.info("[EXPLORE] Codebase research")
        explore_result = await run_explore(plan=plan, config=config)
        return {
            "phase": "explore",
            "context_length": len(explore_result.context),
            "cost_usd": explore_result.cost_usd,
        }

    if phase == "eng-review":
        logger.info("[ENG_REVIEW] Senior engineer review")
        diff_proc = subprocess.run(
            ["git", "diff", config.base_branch],
            capture_output=True,
            text=True,
            cwd=config.cwd,
        )
        name_proc = subprocess.run(
            ["git", "diff", "--name-only", config.base_branch],
            capture_output=True,
            text=True,
            cwd=config.cwd,
        )
        changed_files = [f.strip() for f in name_proc.stdout.strip().splitlines() if f.strip()]
        result = await run_eng_review(
            full_diff=diff_proc.stdout,
            changed_files=changed_files,
            config=config,
        )
        return {
            "phase": "eng-review",
            "findings_count": len(result.findings),
            "risk_summary": result.risk_summary,
            "verdict": result.verdict,
            "cost_usd": result.cost_usd,
            "result": asdict(result),
        }

    if phase == "final-review":
        logger.info("[FINAL_REVIEW] Running final review")
        result = await run_final_review(config)
        return {
            "phase": "final-review",
            "verdict": result.verdict,
            "result": asdict(result),
        }

    # --- Per-step phases (--step required) ---

    if step_num is None:
        logger.error("--step is required for phase '%s'", phase)
        return {"error": f"--step is required for phase '{phase}'"}

    step = next((s for s in plan.steps if s.number == step_num), None)
    if step is None:
        logger.error("Step %d not found in plan", step_num)
        return {"error": f"Step {step_num} not found in plan"}

    prior_files = []
    for s in plan.steps:
        if s.number < step_num:
            prior_files.extend(s.files)

    # --- Load vault context if available ---
    vault_context = ""
    vault_run_id = getattr(args, "vault_run", None)
    if vault_run_id and step_num:
        try:
            manifest = RunManifest(
                plan_slug=plan_slug(config.plan_path),
                run_id=vault_run_id,
                plan_path=config.plan_path,
            )
            vault_context = load_context_for_step(
                plan_path=config.plan_path,
                current_manifest=manifest,
                step_number=step_num,
            )
            if vault_context:
                logger.info("[VAULT] Loaded %d chars of context", len(vault_context))
        except Exception as exc:
            logger.warning("[VAULT] Failed to load context: %s", exc)

    if phase == "implement":
        logger.info("[IMPLEMENT] Step %d — writing code and tests", step_num)
        implement_result = await run_implement(
            step=step,
            plan_text=plan.raw_text,
            config=config,
            prior_files=prior_files,
            vault_context=vault_context,
        )
        return {
            "phase": "implement",
            "step": step_num,
            "test_files": implement_result.test_files,
            "changed_files": implement_result.changed_files,
            "cost_usd": implement_result.cost_usd,
        }

    elif phase == "verify":
        logger.info("[VERIFY] Step %d — lint + tests", step_num)
        test_dir = _find_test_dir(step.files, config.cwd)
        verify_result = run_verify(
            test_dir=test_dir, config=config, changed_files=step.files,
        )
        return {
            "phase": "verify",
            "step": step_num,
            "passed": verify_result.passed,
            "num_tests": verify_result.num_tests,
            "num_failures": verify_result.num_failures,
            "failures": verify_result.failures,
        }

    elif phase == "review":
        logger.info("[REVIEW] Step %d — LLM convention review", step_num)
        diff_proc = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=config.cwd,
        )
        review_result = await run_review(
            diff=diff_proc.stdout,
            changed_files=step.files,
            config=config,
        )
        return {
            "phase": "review",
            "step": step_num,
            "findings_count": len(review_result.findings),
            "has_critical_or_high": review_result.has_critical_or_high,
            "cost_usd": review_result.cost_usd,
            "result": asdict(review_result),
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

    if args.cwd:
        cwd = str(Path(args.cwd).resolve())
    else:
        cwd = _detect_repo_root()

    plan_path = _resolve_plan_path(args.plan, cwd)

    config = PipelineConfig(
        plan_path=plan_path,
        step=args.step,
        review_mode=args.review_mode,
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
    is_failure = result.get("passed") is False or result.get("has_critical_or_high") is True
    return 1 if (is_error or is_failure) else 0


if __name__ == "__main__":
    sys.exit(main())

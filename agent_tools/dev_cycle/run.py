"""Full TDD dev-cycle pipeline runner (headless).

Usage:
    uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md
    uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md --step 3
    uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md --dry-run

Exit code 0 = success, 1 = failure.
Human-readable summary to stderr, structured JSON to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from config import PipelineConfig
from pipeline import run_pipeline
from schemas import PipelineResult

logger = logging.getLogger(__name__)


def _resolve_plan_path(plan_path: str, cwd: str) -> str:
    """Resolve plan_path relative to the repo root, not the script dir.

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


def _build_config(args: argparse.Namespace) -> PipelineConfig:
    """Build a PipelineConfig from parsed CLI arguments.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Configured PipelineConfig instance.
    """
    cwd = str(Path(__file__).resolve().parent.parent.parent)
    plan_path = _resolve_plan_path(args.plan, cwd)

    return PipelineConfig(
        plan_path=plan_path,
        step=args.step,
        max_verify_attempts=args.max_verify,
        max_lint_attempts=args.max_lint,
        dry_run=args.dry_run,
        cwd=cwd,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the full pipeline runner.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Run the full TDD dev-cycle pipeline (headless).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Full pipeline
  uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md

  # Resume from step 3
  uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md --step 3

  # Override limits
  uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md --max-verify 5

  # Dry run (validate plan only)
  uv run --directory agent_tools/dev_cycle python run.py --plan plans/foo.md --dry-run
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
        help="Resume from a specific step number (default: run all steps).",
    )
    parser.add_argument(
        "--max-verify",
        type=int,
        default=3,
        help="Max verify retry attempts per step (default: 3).",
    )
    parser.add_argument(
        "--max-lint",
        type=int,
        default=3,
        help="Max lint/format fix cycles per step (default: 3).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate plan structure only, don't execute.",
    )
    return parser


def _print_summary(result: PipelineResult) -> None:
    """Print a human-readable summary to stderr.

    Args:
        result: The pipeline result to summarize.
    """
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"Pipeline Status: {result.status.upper()}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    for step in result.steps:
        verify_status = "PASS" if step.verify and step.verify.passed else "FAIL"
        lint_status = "PASS" if step.lint and step.lint.passed else "FAIL"
        print(
            f"  Step {step.step_number}: verify={verify_status} lint={lint_status} "
            f"attempts={step.attempts} cost=${step.cost_usd:.4f}",
            file=sys.stderr,
        )

    if result.final_review:
        print(f"  Final Review: {result.final_review.verdict}", file=sys.stderr)

    print(f"  Total Cost: ${result.total_cost_usd:.4f}", file=sys.stderr)

    if result.failure_detail:
        print(f"  Failure: {result.failure_detail}", file=sys.stderr)

    if result.pr_url:
        print(f"  PR: {result.pr_url}", file=sys.stderr)

    print(f"{'=' * 60}\n", file=sys.stderr)


def main() -> int:
    """CLI entry point for the full pipeline runner.

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
    config = _build_config(args)

    logger.info("Starting pipeline for plan: %s", config.plan_path)
    if config.dry_run:
        logger.info("Dry run mode — validating plan only.")

    try:
        result = asyncio.run(run_pipeline(config))
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user.")
        result = PipelineResult(
            status="failed",
            failure_detail="Interrupted by user (KeyboardInterrupt).",
        )

    _print_summary(result)

    # Structured JSON to stdout
    json.dump(asdict(result), sys.stdout, indent=2, default=str)
    print(file=sys.stdout)

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

"""Command-line interface for CLAUDE.md evaluation framework."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class ProblemsAction(argparse.Action):
    """Custom action to parse comma-separated problems into a list."""

    def __call__(self, parser, namespace, values, option_string=None):
        if values == "all":
            setattr(namespace, self.dest, ["all"])
        else:
            problems = [p.strip() for p in values.split(",") if p.strip()]
            setattr(namespace, self.dest, problems)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance ready for parsing command-line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="claude-md-eval",
        description="Evaluate CLAUDE.md files using coding problems and LLM-as-judge scoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-md-eval CLAUDE.md
  claude-md-eval project1/CLAUDE.md project2/CLAUDE.md --problems lru_cache,csv_parser
  claude-md-eval *.md --output-dir ./results --problems all
        """,
    )

    parser.add_argument(
        "claude_md_files",
        nargs="+",
        type=Path,
        metavar="CLAUDE_MD_FILE",
        help="One or more CLAUDE.md file paths to evaluate",
    )

    parser.add_argument(
        "--problems",
        action=ProblemsAction,
        default=["all"],
        metavar="PROBLEM_LIST",
        help="Comma-separated list of problem names to run, or 'all' (default: all)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./evaluations"),
        metavar="OUTPUT_DIR",
        help="Directory to write evaluation reports (default: ./evaluations)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        metavar="SECONDS",
        help="Maximum seconds per code generation call (default: 120)",
    )

    parser.add_argument(
        "--rubric",
        type=Path,
        default=None,
        metavar="RUBRIC_PATH",
        help="Path to a custom rubric YAML file (default: built-in rubric)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output",
    )

    return parser


def _validate_claude_md_files(files: list[Path]) -> None:
    """Validate that CLAUDE.md files exist and have proper extension.

    Args:
        files: List of Path objects to validate.

    Raises:
        SystemExit: If any file is invalid.
    """
    for file_path in files:
        # Check file extension
        if file_path.suffix.lower() != ".md":
            logger.error("File must have .md extension: %s", file_path)
            sys.exit(1)

        # Check file existence
        if not file_path.exists():
            logger.error("File does not exist: %s", file_path)
            sys.exit(1)

        if not file_path.is_file():
            logger.error("Path is not a file: %s", file_path)
            sys.exit(1)


def _validate_problems(problems: list[str]) -> list[str]:
    """Validate problem names.

    Args:
        problems: List of problem names.

    Returns:
        List of validated problem names.

    Raises:
        SystemExit: If any problem name is invalid.
    """
    if problems == ["all"]:
        return ["all"]

    for problem in problems:
        if not problem:
            logger.error("Empty problem name in list")
            sys.exit(1)

        # Check if problem name is a valid identifier (letters, digits, underscores)
        if not problem.replace("_", "").replace("-", "").isalnum():
            logger.error("Invalid problem name (must be alphanumeric with _ or -): %s", problem)
            sys.exit(1)

        # Additional check for problematic characters
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        invalid_chars = set(problem) - valid_chars
        if invalid_chars:
            logger.error("Invalid characters in problem name '%s': %s", problem, invalid_chars)
            sys.exit(1)

    return problems


def _setup_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging based on verbosity settings.

    Args:
        verbose: Enable verbose logging.
        quiet: Enable quiet mode (errors only).
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_evaluation(
    claude_md_files: list[Path],
    problems: list[str],
    output_dir: Path,
    rubric_path: Path | None = None,
    timeout: int = 120,
) -> None:
    """Run the full evaluation pipeline via the async orchestrator.

    Resolves problem names to Problem objects, then delegates to the
    orchestrator's ``run_evaluation`` coroutine.

    Args:
        claude_md_files: List of CLAUDE.md file paths to evaluate.
        problems: List of problem names to run (or ``["all"]``).
        output_dir: Directory to write evaluation reports.
        rubric_path: Optional path to a custom rubric YAML file.
        timeout: Maximum seconds per code generation call.

    Raises:
        RuntimeError: If evaluation fails.
    """
    from evaluator.orchestrator import resolve_problems
    from evaluator.orchestrator import run_evaluation as _orchestrator_run

    resolved = resolve_problems(problems)

    report_paths = asyncio.run(
        _orchestrator_run(
            claude_md_files=claude_md_files,
            problems=resolved,
            output_dir=output_dir,
            rubric_path=rubric_path,
            timeout=timeout,
        )
    )

    for rp in report_paths:
        logger.info("Report: %s", rp)


def main(args: Sequence[str] | None = None) -> int:
    """Main CLI entry point.

    Parses arguments, validates inputs, and delegates to
    :func:`run_evaluation`.

    Args:
        args: Command-line arguments to parse. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Setup logging
    _setup_logging(parsed_args.verbose, parsed_args.quiet)

    try:
        # Validate inputs
        _validate_claude_md_files(parsed_args.claude_md_files)
        problem_names = _validate_problems(parsed_args.problems)

        # Create output directory if it doesn't exist
        parsed_args.output_dir.mkdir(parents=True, exist_ok=True)

        # Validate rubric path if provided
        if parsed_args.rubric is not None and not parsed_args.rubric.is_file():
            logger.error("Rubric file does not exist: %s", parsed_args.rubric)
            sys.exit(1)

        # Run evaluation
        run_evaluation(
            parsed_args.claude_md_files,
            problem_names,
            parsed_args.output_dir,
            rubric_path=parsed_args.rubric,
            timeout=parsed_args.timeout,
        )

    except KeyboardInterrupt:
        logger.exception("Evaluation interrupted by user")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Evaluation failed")
        sys.exit(1)
    else:
        logger.info("Evaluation completed successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())

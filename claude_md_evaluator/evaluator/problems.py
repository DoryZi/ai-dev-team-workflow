"""Problem discovery and loading for the evaluation framework.

Discovers built-in and custom coding problems that are used to evaluate
CLAUDE.md files. Each problem consists of a prompt, reference solution,
and test suite.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILTIN_PROBLEMS_DIR = Path(__file__).parent.parent / "problems"

_REQUIRED_FILES = ("prompt.md", "reference_solution.py")
_REQUIRED_DIRS = ("tests",)


@dataclass(frozen=True)
class Problem:
    """A coding problem used for CLAUDE.md evaluation.

    Attributes:
        name: Unique identifier for the problem (directory name).
        prompt: The full prompt text that will be sent to the LLM.
        test_dir: Path to the directory containing test files.
        reference_solution_path: Path to the known-good reference solution.
    """

    name: str
    prompt: str
    test_dir: Path
    reference_solution_path: Path


def load_problem(problem_dir: Path) -> Problem:
    """Load a single problem from its directory.

    Reads the prompt and validates that required files and directories
    exist within the problem folder.

    Args:
        problem_dir: Path to the problem directory containing prompt.md,
            reference_solution.py, and tests/.

    Returns:
        A fully populated Problem instance.

    Raises:
        FileNotFoundError: If the problem directory or required files are missing.
        ValueError: If the problem directory structure is invalid.
    """
    if not problem_dir.is_dir():
        raise FileNotFoundError(f"Problem directory does not exist: {problem_dir}")

    # Validate required files
    for filename in _REQUIRED_FILES:
        file_path = problem_dir / filename
        if not file_path.is_file():
            raise ValueError(
                f"Problem '{problem_dir.name}' is missing required file: {filename}"
            )

    # Validate required directories
    for dirname in _REQUIRED_DIRS:
        dir_path = problem_dir / dirname
        if not dir_path.is_dir():
            raise ValueError(
                f"Problem '{problem_dir.name}' is missing required directory: {dirname}"
            )

    # Validate tests directory has at least one test file
    test_dir = problem_dir / "tests"
    test_files = list(test_dir.glob("test_*.py"))
    if not test_files:
        raise ValueError(
            f"Problem '{problem_dir.name}' has no test files (test_*.py) in tests/"
        )

    prompt_text = (problem_dir / "prompt.md").read_text(encoding="utf-8")
    reference_path = problem_dir / "reference_solution.py"

    logger.debug("Loaded problem: %s", problem_dir.name)

    return Problem(
        name=problem_dir.name,
        prompt=prompt_text,
        test_dir=test_dir,
        reference_solution_path=reference_path,
    )


def discover_problems(problems_dir: Path) -> list[Problem]:
    """Discover and load all problems from a directory.

    Scans the given directory for subdirectories that contain valid
    problem structures (prompt.md, reference_solution.py, tests/).

    Args:
        problems_dir: Path to the directory containing problem subdirectories.

    Returns:
        List of Problem instances, sorted by name.

    Raises:
        FileNotFoundError: If the problems directory does not exist.
    """
    if not problems_dir.is_dir():
        raise FileNotFoundError(f"Problems directory does not exist: {problems_dir}")

    problems: list[Problem] = []

    for candidate in sorted(problems_dir.iterdir()):
        if not candidate.is_dir():
            continue

        # Skip hidden directories and __pycache__
        if candidate.name.startswith(".") or candidate.name.startswith("__"):
            continue

        try:
            problem = load_problem(candidate)
            problems.append(problem)
        except (ValueError, FileNotFoundError) as exc:
            logger.warning("Skipping invalid problem directory '%s': %s", candidate.name, exc)

    logger.info("Discovered %d problems in %s", len(problems), problems_dir)
    return problems


def get_builtin_problems() -> list[Problem]:
    """Return all built-in problems shipped with the package.

    Returns:
        List of built-in Problem instances, sorted by name.

    Raises:
        FileNotFoundError: If the built-in problems directory is missing.
    """
    if not _BUILTIN_PROBLEMS_DIR.is_dir():
        raise FileNotFoundError(
            f"Built-in problems directory not found: {_BUILTIN_PROBLEMS_DIR}"
        )

    return discover_problems(_BUILTIN_PROBLEMS_DIR)

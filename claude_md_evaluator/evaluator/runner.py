"""Code generation runner that invokes claude CLI in an isolated environment.

Creates a temporary directory with a CLAUDE.md file, runs `claude -p` with a
problem prompt, extracts Python code from the output, and writes it as
solution.py for downstream test execution.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationResult:
    """Result of a code generation run.

    Attributes:
        solution_code: The extracted Python code from claude's output.
        solution_path: Path to solution.py written in the temp directory.
        raw_output: Full raw output from the claude CLI invocation.
        duration_seconds: Wall-clock time in seconds for the generation run.
        temp_dir: Temporary directory containing all generated artifacts.
            The caller is responsible for cleanup.
        success: Whether Python code was successfully extracted and written.
    """

    solution_code: str
    solution_path: Path
    raw_output: str
    duration_seconds: float
    temp_dir: Path
    success: bool


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

_CODE_BLOCK_PATTERN = re.compile(
    r"```python\s*\n(.*?)```",
    re.DOTALL,
)


def extract_python_code(raw_output: str) -> str:
    """Extract Python code from markdown-formatted claude output.

    Finds all ```python ... ``` fenced code blocks and concatenates them
    with blank lines between blocks. This handles outputs that split imports,
    classes, and functions across multiple blocks.

    Args:
        raw_output: Raw text output from the claude CLI.

    Returns:
        Concatenated Python source code, or empty string if no blocks found.
    """
    blocks = _CODE_BLOCK_PATTERN.findall(raw_output)
    if not blocks:
        return ""

    cleaned = [block.strip() for block in blocks]
    return "\n\n".join(cleaned) + "\n"


# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------


def _setup_temp_dir(
    claude_md_path: Path,
    problem_test_dir: Path,
) -> Path:
    """Create and populate a temporary working directory.

    Copies the CLAUDE.md file and the problem's test files into a fresh
    temp directory for isolated code generation and testing.

    Args:
        claude_md_path: Path to the CLAUDE.md file to evaluate.
        problem_test_dir: Path to the problem's tests/ directory.

    Returns:
        Path to the newly created temporary directory.

    Raises:
        FileNotFoundError: If claude_md_path or problem_test_dir does not exist.
    """
    if not claude_md_path.is_file():
        raise FileNotFoundError(f"CLAUDE.md not found: {claude_md_path}")
    if not problem_test_dir.is_dir():
        raise FileNotFoundError(f"Test directory not found: {problem_test_dir}")

    temp_dir = Path(tempfile.mkdtemp(prefix="claude_eval_"))

    # Copy CLAUDE.md into temp dir root
    shutil.copy2(claude_md_path, temp_dir / "CLAUDE.md")

    # Copy test files into tests/ subdirectory
    tests_dest = temp_dir / "tests"
    shutil.copytree(problem_test_dir, tests_dest)

    logger.debug("Created temp directory: %s", temp_dir)
    return temp_dir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_solution(
    claude_md_path: Path,
    problem: object,
    timeout: int = 120,
) -> GenerationResult:
    """Generate a solution for a coding problem using the claude CLI.

    Creates an isolated temporary directory, copies in the CLAUDE.md file
    and problem test files, then invokes ``claude -p`` with the problem
    prompt. Extracts Python code from the response and writes it to
    ``solution.py`` in the temp directory.

    Args:
        claude_md_path: Path to the CLAUDE.md file being evaluated.
        problem: A Problem instance with ``prompt``, ``test_dir``, and
            ``name`` attributes.
        timeout: Maximum seconds to wait for the claude CLI. Defaults to 120.

    Returns:
        A GenerationResult describing the outcome. On failure (timeout,
        subprocess error, no code extracted), ``success`` is False but
        the result is still returned with whatever information is available.
    """
    # Access problem attributes (duck-typed to avoid circular import)
    prompt: str = problem.prompt  # type: ignore[attr-defined]
    test_dir: Path = problem.test_dir  # type: ignore[attr-defined]
    problem_name: str = problem.name  # type: ignore[attr-defined]

    logger.info("Generating solution for problem: %s", problem_name)

    temp_dir = _setup_temp_dir(claude_md_path, test_dir)
    solution_path = temp_dir / "solution.py"

    start_time = time.monotonic()
    raw_output = ""
    success = False
    solution_code = ""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(temp_dir),
        )
        raw_output = result.stdout
        if result.returncode != 0:
            logger.warning(
                "claude CLI exited with code %d for problem '%s': %s",
                result.returncode,
                problem_name,
                result.stderr[:500] if result.stderr else "(no stderr)",
            )

    except subprocess.TimeoutExpired as exc:
        raw_output = (exc.stdout or b"").decode("utf-8", errors="replace") if exc.stdout else ""
        logger.warning(
            "claude CLI timed out after %ds for problem '%s'",
            timeout,
            problem_name,
        )
    except FileNotFoundError:
        logger.error(
            "claude CLI not found on PATH. Install it before running evaluations."
        )
    except OSError as exc:
        logger.error("Failed to run claude CLI: %s", exc)

    duration = time.monotonic() - start_time

    # Extract code from output
    solution_code = extract_python_code(raw_output)

    if solution_code:
        solution_path.write_text(solution_code, encoding="utf-8")
        success = True
        logger.info(
            "Extracted solution for '%s' (%d chars, %.1fs)",
            problem_name,
            len(solution_code),
            duration,
        )
    else:
        # Write empty file so downstream can still report the failure
        solution_path.write_text("# No code extracted from claude output\n", encoding="utf-8")
        logger.warning(
            "No Python code blocks found in claude output for '%s'",
            problem_name,
        )

    return GenerationResult(
        solution_code=solution_code,
        solution_path=solution_path,
        raw_output=raw_output,
        duration_seconds=duration,
        temp_dir=temp_dir,
        success=success,
    )

"""Run problem test suites against generated solutions.

Copies test files into the solution directory and executes pytest via
subprocess, parsing structured JUnit XML output to produce detailed
test results.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TestResult:
    """Result of a single test case.

    Attributes:
        name: Fully qualified test name (e.g. test_module::TestClass::test_func).
        passed: Whether the test passed.
        duration_seconds: Wall-clock time for this individual test.
        error_message: Failure or error details, None if passed.
    """

    name: str
    passed: bool
    duration_seconds: float
    error_message: str | None = None


@dataclass(frozen=True)
class TestRunResult:
    """Aggregate result of running all tests for a problem.

    Attributes:
        passed: True only if every test passed.
        total_tests: Number of tests discovered and run.
        passed_tests: Number of tests that passed.
        failed_tests: Number of tests that failed or errored.
        test_results: Per-test breakdown.
        duration_seconds: Total wall-clock time for the entire run.
        stdout: Raw pytest stdout.
        stderr: Raw pytest stderr.
    """

    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    test_results: list[TestResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""


def _parse_junit_xml(xml_path: Path) -> list[TestResult]:
    """Parse a JUnit XML file into a list of TestResult objects.

    Args:
        xml_path: Path to the pytest-generated JUnit XML report.

    Returns:
        List of TestResult, one per test case found in the XML.
    """
    if not xml_path.is_file():
        logger.warning("JUnit XML not found at %s", xml_path)
        return []

    try:
        tree = ET.parse(xml_path)  # noqa: S314
    except ET.ParseError as exc:
        logger.error("Failed to parse JUnit XML: %s", exc)
        return []

    root = tree.getroot()
    results: list[TestResult] = []

    # pytest generates <testcase> elements under <testsuite>
    for testcase in root.iter("testcase"):
        name = testcase.get("classname", "") + "::" + testcase.get("name", "")
        duration = float(testcase.get("time", "0"))

        failure = testcase.find("failure")
        error = testcase.find("error")

        if failure is not None:
            error_msg = failure.get("message", "") or failure.text or "Test failed"
            results.append(
                TestResult(
                    name=name,
                    passed=False,
                    duration_seconds=duration,
                    error_message=error_msg,
                )
            )
        elif error is not None:
            error_msg = error.get("message", "") or error.text or "Test error"
            results.append(
                TestResult(
                    name=name,
                    passed=False,
                    duration_seconds=duration,
                    error_message=error_msg,
                )
            )
        else:
            results.append(
                TestResult(name=name, passed=True, duration_seconds=duration)
            )

    return results


def _copy_test_files(problem_test_dir: Path, solution_dir: Path) -> list[Path]:
    """Copy test files from the problem into the solution directory.

    Creates a tests/ subdirectory inside solution_dir and copies all
    Python test files into it.

    Args:
        problem_test_dir: Source directory containing test_*.py files.
        solution_dir: Target directory where solution.py lives.

    Returns:
        List of paths to copied files (inside solution_dir/tests/).
    """
    target_tests_dir = solution_dir / "tests"
    target_tests_dir.mkdir(exist_ok=True)

    copied: list[Path] = []
    for src_file in problem_test_dir.iterdir():
        if src_file.is_file() and src_file.suffix == ".py":
            dest = target_tests_dir / src_file.name
            shutil.copy2(src_file, dest)
            copied.append(dest)
            logger.debug("Copied test file: %s -> %s", src_file, dest)

    return copied


def _make_timeout_result(timeout: int, stdout: str, stderr: str) -> TestRunResult:
    """Build a TestRunResult for a timed-out test run.

    Args:
        timeout: The timeout value in seconds that was exceeded.
        stdout: Any captured stdout before timeout.
        stderr: Any captured stderr before timeout.

    Returns:
        A TestRunResult indicating timeout failure.
    """
    return TestRunResult(
        passed=False,
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        test_results=[],
        duration_seconds=float(timeout),
        stdout=stdout,
        stderr=f"Test run timed out after {timeout} seconds.\n{stderr}",
    )


def run_tests(
    solution_dir: Path,
    problem_test_dir: Path,
    timeout: int = 30,
) -> TestRunResult:
    """Run problem tests against a generated solution.

    Copies test files from problem_test_dir into solution_dir/tests/,
    executes pytest via subprocess, and parses structured JUnit XML output
    to build a detailed TestRunResult.

    Args:
        solution_dir: Directory containing solution.py (the generated code).
        problem_test_dir: Directory containing test_*.py files for the problem.
        timeout: Maximum seconds to allow the test run before killing it.

    Returns:
        TestRunResult with per-test details and aggregate counts.
    """
    if not solution_dir.is_dir():
        raise FileNotFoundError(f"Solution directory does not exist: {solution_dir}")
    if not problem_test_dir.is_dir():
        raise FileNotFoundError(f"Problem test directory does not exist: {problem_test_dir}")

    # Copy test files into solution directory
    copied_files = _copy_test_files(problem_test_dir, solution_dir)
    if not copied_files:
        logger.warning("No test files found in %s", problem_test_dir)
        return TestRunResult(
            passed=False,
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            test_results=[],
            duration_seconds=0.0,
            stdout="",
            stderr=f"No test files found in {problem_test_dir}",
        )

    junit_xml_path = solution_dir / "junit_results.xml"

    cmd = [
        "python",
        "-m",
        "pytest",
        str(solution_dir / "tests"),
        "--tb=short",
        "-v",
        f"--junit-xml={junit_xml_path}",
        "--no-header",
        "-q",
    ]

    logger.info("Running tests in %s (timeout=%ds)", solution_dir, timeout)
    start_time = time.monotonic()

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(solution_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=None,  # inherit parent environment
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start_time
        logger.warning("Test run timed out after %.1fs", elapsed)
        return _make_timeout_result(
            timeout=timeout,
            stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr or "" if isinstance(exc.stderr, str) else "",
        )

    elapsed = time.monotonic() - start_time
    logger.info(
        "pytest exited with code %d in %.2fs", proc.returncode, elapsed
    )

    # Parse JUnit XML for structured results
    test_results = _parse_junit_xml(junit_xml_path)

    passed_count = sum(1 for r in test_results if r.passed)
    failed_count = sum(1 for r in test_results if not r.passed)
    total_count = len(test_results)

    return TestRunResult(
        passed=proc.returncode == 0 and failed_count == 0,
        total_tests=total_count,
        passed_tests=passed_count,
        failed_tests=failed_count,
        test_results=test_results,
        duration_seconds=elapsed,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )

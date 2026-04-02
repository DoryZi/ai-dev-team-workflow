"""Phase execution functions for the dev-cycle pipeline.

Each function runs one phase of the TDD cycle and returns a typed result.
Agent phases (RED, GREEN) use the Claude Agent SDK to spawn sub-agents.
Mechanical phases (VERIFY, LINT) use subprocess calls.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from claude_agent_sdk import Agent, run_agent

from agents import make_sde_agent, make_test_eng_agent
from checks.conventions_loader import get_conventions_for_step
from checks.static_checks import check_files
from config import PipelineConfig
from plan_parser import PlanStep
from schemas import (
    GreenResult,
    LintResult,
    RedResult,
    ReviewResult,
    VerifyResult,
)

logger = logging.getLogger(__name__)


async def run_red(
    step: PlanStep,
    plan_text: str,
    config: PipelineConfig,
    prior_files: list[str],
) -> RedResult:
    """Execute the RED phase — test-eng writes failing tests.

    Args:
        step: The plan step to write tests for.
        plan_text: Full plan markdown text.
        config: Pipeline configuration.
        prior_files: Files from previously completed steps.

    Returns:
        RedResult with test file paths and cost.
    """
    logger.info("[RED] Step %d — writing tests", step.number)

    conventions = get_conventions_for_step(step.files, Path(config.cwd))
    agent_config = make_test_eng_agent(
        step=step,
        conventions=conventions,
        plan_text=plan_text,
        prior_files=prior_files,
    )

    agent = Agent(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

    result = await run_agent(agent)

    # Extract test file paths from agent output
    test_files = _extract_file_paths(result.output, pattern=r"test.*\.py")

    logger.info("[RED] Step %d — %d test files written", step.number, len(test_files))

    return RedResult(
        test_files=test_files,
        cost_usd=result.cost_usd,
    )


async def run_green(
    step: PlanStep,
    plan_text: str,
    test_files: list[str],
    config: PipelineConfig,
    prior_files: list[str],
    extra_context: str = "",
) -> GreenResult:
    """Execute the GREEN phase — SDE implements production code.

    Args:
        step: The plan step to implement.
        plan_text: Full plan markdown text.
        test_files: Paths to test files (the spec for this step).
        config: Pipeline configuration.
        prior_files: Files from previously completed steps.
        extra_context: Optional context (e.g. previous failure output).

    Returns:
        GreenResult with changed file paths and cost.
    """
    logger.info("[GREEN] Step %d — implementing", step.number)

    conventions = get_conventions_for_step(step.files, Path(config.cwd))
    agent_config = make_sde_agent(
        step=step,
        conventions=conventions,
        plan_text=plan_text,
        test_files=test_files,
        prior_files=prior_files,
        extra_context=extra_context,
    )

    agent = Agent(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

    result = await run_agent(agent)

    # Extract changed file paths from agent output
    changed_files = _extract_file_paths(result.output, pattern=r"\.py")

    logger.info("[GREEN] Step %d — %d files changed", step.number, len(changed_files))

    return GreenResult(
        changed_files=changed_files,
        cost_usd=result.cost_usd,
    )


async def run_green_fix(
    step: PlanStep,
    plan_text: str,
    test_files: list[str],
    failure_output: str,
    config: PipelineConfig,
    prior_files: list[str],
) -> GreenResult:
    """Execute a GREEN fix — SDE fixes code based on test failures.

    Args:
        step: The plan step being fixed.
        plan_text: Full plan markdown text.
        test_files: Paths to test files.
        failure_output: Test failure output to help SDE fix the code.
        config: Pipeline configuration.
        prior_files: Files from previously completed steps.

    Returns:
        GreenResult with changed file paths and cost.
    """
    extra_context = f"""## Test Failures (fix these)

The following tests are failing. Fix the production code to make them pass.
Do NOT modify test files.

```
{failure_output}
```"""

    return await run_green(
        step=step,
        plan_text=plan_text,
        test_files=test_files,
        config=config,
        prior_files=prior_files,
        extra_context=extra_context,
    )


def run_verify(
    test_dir: str,
    config: PipelineConfig,
) -> VerifyResult:
    """Execute the VERIFY phase — run pytest.

    Args:
        test_dir: Directory containing the project with tests.
        config: Pipeline configuration.

    Returns:
        VerifyResult with pass/fail status and failure details.
    """
    logger.info("[VERIFY] Running pytest in %s", test_dir)

    proc = subprocess.run(
        ["uv", "run", "--directory", test_dir, "python", "-m", "pytest", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=config.cwd,
        timeout=120,
    )

    passed = proc.returncode == 0
    output = proc.stdout + proc.stderr

    # Parse pytest output for counts
    num_tests, num_failures = _parse_pytest_summary(output)
    failures = _parse_pytest_failures(output) if not passed else []

    logger.info(
        "[VERIFY] %s — %d tests, %d failures",
        "PASSED" if passed else "FAILED",
        num_tests,
        num_failures,
    )

    return VerifyResult(
        passed=passed,
        num_tests=num_tests,
        num_failures=num_failures,
        failures=failures,
    )


def run_lint(
    changed_files: list[str],
    config: PipelineConfig,
) -> LintResult:
    """Execute the LINT phase — ruff format + ruff check.

    First runs ``ruff format`` to auto-fix formatting, then runs
    ``ruff check --fix`` to auto-fix lint violations, then checks
    for any remaining issues.

    Args:
        changed_files: List of file paths to lint.
        config: Pipeline configuration.

    Returns:
        LintResult with pass/fail status and violation details.
    """
    logger.info("[LINT] Checking %d files", len(changed_files))

    if not changed_files:
        return LintResult(passed=True)

    # Filter to Python files that exist
    py_files = [
        f for f in changed_files
        if f.endswith(".py") and (Path(config.cwd) / f).is_file()
    ]

    if not py_files:
        return LintResult(passed=True)

    violations: list[str] = []

    # Run ruff format (auto-fix)
    subprocess.run(
        ["ruff", "format", *py_files],
        cwd=config.cwd,
        capture_output=True,
        text=True,
    )

    # Run ruff check --fix (auto-fix lint)
    subprocess.run(
        ["ruff", "check", "--fix", *py_files],
        cwd=config.cwd,
        capture_output=True,
        text=True,
    )

    # Check for remaining violations
    format_check = subprocess.run(
        ["ruff", "format", "--check", *py_files],
        cwd=config.cwd,
        capture_output=True,
        text=True,
    )
    if format_check.returncode != 0:
        violations.append(f"ruff format: {format_check.stdout.strip()}")

    lint_check = subprocess.run(
        ["ruff", "check", *py_files],
        cwd=config.cwd,
        capture_output=True,
        text=True,
    )
    if lint_check.returncode != 0:
        violations.append(f"ruff check: {lint_check.stdout.strip()}")

    passed = len(violations) == 0

    logger.info("[LINT] %s — %d violations", "PASSED" if passed else "FAILED", len(violations))

    return LintResult(passed=passed, violations=violations)


def run_final_review(
    config: PipelineConfig,
) -> ReviewResult:
    """Execute the FINAL_REVIEW phase — static checks + /review.

    Runs mechanical static checks on all changed files, then invokes
    the ``/review`` skill via the Claude CLI for a full code review.

    Args:
        config: Pipeline configuration.

    Returns:
        ReviewResult with findings, verdict, and summary.
    """
    logger.info("[FINAL_REVIEW] Running static checks + /review")

    # Get changed files from git
    diff_proc = subprocess.run(
        ["git", "diff", "--name-only", config.base_branch],
        capture_output=True,
        text=True,
        cwd=config.cwd,
    )
    changed_files = [f.strip() for f in diff_proc.stdout.strip().splitlines() if f.strip()]

    # Run static checks
    static_violations = check_files(changed_files, config.cwd)
    static_summary = f"{len(static_violations)} static check violations"
    if static_violations:
        static_details = "\n".join(
            f"  {v.file}:{v.line} [{v.rule}] {v.message}"
            for v in static_violations
        )
        logger.info("[FINAL_REVIEW] Static checks:\n%s", static_details)

    # Invoke /review via Claude CLI
    review_context = ""
    if static_violations:
        review_context = "Static check findings (already flagged — focus on contextual issues):\n"
        review_context += "\n".join(f"- {v.rule}: {v.message} ({v.file}:{v.line})" for v in static_violations)

    review_proc = subprocess.run(
        [
            "claude",
            "--print",
            "--allowedTools", "Read,Glob,Grep",
            "-p", f"Run /review on the current branch diff against {config.base_branch}. "
                  f"Additional context: {review_context}" if review_context else
                  f"Run /review on the current branch diff against {config.base_branch}.",
        ],
        capture_output=True,
        text=True,
        cwd=config.cwd,
        timeout=300,
    )

    review_output = review_proc.stdout

    # Parse verdict from review output
    verdict = "APPROVE"
    if "BLOCK" in review_output.upper():
        verdict = "BLOCK"
    elif "WARNING" in review_output.upper():
        verdict = "WARNING"

    summary = f"{static_summary}. Review verdict: {verdict}"

    logger.info("[FINAL_REVIEW] %s", summary)

    return ReviewResult(
        findings=[{"static_violations": len(static_violations)}],
        verdict=verdict,
        summary=summary,
    )


def _extract_file_paths(output: str, pattern: str) -> list[str]:
    """Extract file paths from agent output text.

    Looks for lines containing file paths matching the given pattern.

    Args:
        output: Agent output text.
        pattern: Regex pattern to match in file paths.

    Returns:
        Deduplicated list of file paths found.
    """
    paths: list[str] = []
    path_re = re.compile(r"(?:^|\s)([a-zA-Z0-9_/.-]+(?:" + pattern + r"))", re.MULTILINE)
    for match in path_re.finditer(output):
        path = match.group(1).strip()
        if path not in paths:
            paths.append(path)
    return paths


def _parse_pytest_summary(output: str) -> tuple[int, int]:
    """Parse pytest summary line for test counts.

    Args:
        output: Full pytest output text.

    Returns:
        Tuple of (total_tests, num_failures).
    """
    # Match patterns like "5 passed", "3 failed", "2 passed, 1 failed"
    passed = 0
    failed = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    return passed + failed, failed


def _parse_pytest_failures(output: str) -> list[str]:
    """Extract failure descriptions from pytest output.

    Args:
        output: Full pytest output text.

    Returns:
        List of failure description strings.
    """
    failures: list[str] = []
    # Match FAILED lines like "FAILED tests/test_foo.py::test_bar - AssertionError"
    for match in re.finditer(r"FAILED\s+(.+?)(?:\s+-\s+(.+))?$", output, re.MULTILINE):
        test_name = match.group(1).strip()
        reason = match.group(2).strip() if match.group(2) else "unknown"
        failures.append(f"{test_name}: {reason}")
    return failures

"""Phase execution functions for the dev-cycle pipeline.

Each function runs one phase of the TDD cycle and returns a typed result.
Agent phases (RED, GREEN, REVIEW, ENG-REVIEW, EXPLORE) use the Claude Agent
SDK ``query()`` — each call is an isolated, stateless session. The pipeline
orchestrator manages all inter-process communication.
Mechanical phases (VERIFY, LINT) use subprocess calls.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from agents import (
    make_eng_review_agent,
    make_explore_agent,
    make_review_agent,
    make_sde_agent,
    make_test_eng_agent,
)
from checks.conventions_loader import get_conventions_for_step, get_conventions_header
from checks.risk_scorer import score_risk
from checks.static_checks import check_files
from config import PipelineConfig
from plan_parser import Plan, PlanStep
from schemas import (
    AgentReviewResult,
    EngReviewResult,
    ExploreResult,
    GreenResult,
    LintResult,
    RedResult,
    ReviewFinding,
    StaticReviewResult,
    VerifyResult,
)

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result from a single query() call.

    Attributes:
        output: The agent's text output.
        cost_usd: Total cost of the query.
    """

    output: str = ""
    cost_usd: float = 0.0


async def _run_query(
    prompt: str,
    tools: list[str],
    model: str,
    cwd: str,
) -> QueryResult:
    """Run a single isolated query() session.

    Each call is stateless — no conversation history carries over.
    The pipeline manages all context passing between phases.

    Args:
        prompt: Full prompt for the agent.
        tools: List of tool names the agent can use.
        model: Model identifier.
        cwd: Working directory for the session.

    Returns:
        QueryResult with output text and cost.
    """
    options = ClaudeAgentOptions(
        allowed_tools=tools,
        model=model,
        cwd=cwd,
        permission_mode="bypassPermissions",
    )

    output_parts: list[str] = []
    cost_usd = 0.0

    async for event in query(prompt=prompt, options=options):
        if isinstance(event, ResultMessage):
            output_parts.append(event.result or "")
            cost_usd = event.total_cost_usd or 0.0

    return QueryResult(
        output="\n".join(output_parts),
        cost_usd=cost_usd,
    )


async def run_red(
    step: PlanStep,
    plan_text: str,
    config: PipelineConfig,
    prior_files: list[str],
    explore_context: str = "",
) -> RedResult:
    """Execute the RED phase — test-eng writes failing tests.

    Args:
        step: The plan step to write tests for.
        plan_text: Full plan markdown text.
        config: Pipeline configuration.
        prior_files: Files from previously completed steps.
        explore_context: Codebase exploration context from the EXPLORE phase.

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
        explore_context=explore_context,
    )

    result = await _run_query(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

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
    explore_context: str = "",
) -> GreenResult:
    """Execute the GREEN phase — SDE implements production code.

    Args:
        step: The plan step to implement.
        plan_text: Full plan markdown text.
        test_files: Paths to test files (the spec for this step).
        config: Pipeline configuration.
        prior_files: Files from previously completed steps.
        extra_context: Optional context (e.g. previous failure output).
        explore_context: Codebase exploration context from the EXPLORE phase.

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
        explore_context=explore_context,
    )

    result = await _run_query(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

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
    explore_context: str = "",
) -> GreenResult:
    """Execute a GREEN fix — SDE fixes code based on test failures.

    Args:
        step: The plan step being fixed.
        plan_text: Full plan markdown text.
        test_files: Paths to test files.
        failure_output: Test failure output to help SDE fix the code.
        config: Pipeline configuration.
        prior_files: Files from previously completed steps.
        explore_context: Codebase exploration context from the EXPLORE phase.

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
        explore_context=explore_context,
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


async def run_explore(
    plan: Plan,
    config: PipelineConfig,
) -> ExploreResult:
    """Execute the EXPLORE phase — codebase research before implementation.

    Spawns an explorer agent that reads the codebase, past plans, and
    discussions to document patterns, utilities, and risks.

    Args:
        plan: Parsed plan with steps and file lists.
        config: Pipeline configuration.

    Returns:
        ExploreResult with exploration context and cost.
    """
    logger.info("[EXPLORE] Researching codebase")

    all_files = []
    for step in plan.steps:
        all_files.extend(step.files)

    agent_config = make_explore_agent(
        plan_text=plan.raw_text,
        plan_files=all_files,
        cwd=config.cwd,
    )

    result = await _run_query(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

    logger.info("[EXPLORE] Complete — %.0f chars of context", len(result.output))

    return ExploreResult(
        context=result.output,
        cost_usd=result.cost_usd,
    )


async def run_review(
    diff: str,
    changed_files: list[str],
    config: PipelineConfig,
) -> AgentReviewResult:
    """Execute per-step LLM convention review.

    Args:
        diff: Git diff for the step's changes.
        changed_files: List of file paths changed in this step.
        config: Pipeline configuration.

    Returns:
        AgentReviewResult with findings and severity assessment.
    """
    logger.info("[REVIEW] LLM convention review on %d files", len(changed_files))

    conventions = get_conventions_header(Path(config.cwd))
    agent_config = make_review_agent(
        conventions=conventions,
        diff=diff,
        changed_files=changed_files,
    )

    result = await _run_query(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

    findings = _parse_review_findings(result.output)
    has_critical_or_high = any(f.severity in ("CRITICAL", "HIGH") for f in findings)

    logger.info(
        "[REVIEW] %d findings, critical_or_high=%s",
        len(findings),
        has_critical_or_high,
    )

    return AgentReviewResult(
        findings=findings,
        has_critical_or_high=has_critical_or_high,
        cost_usd=result.cost_usd,
    )


async def run_eng_review(
    full_diff: str,
    changed_files: list[str],
    config: PipelineConfig,
) -> EngReviewResult:
    """Execute final LLM engineering review on the full branch diff.

    Args:
        full_diff: Full branch diff.
        changed_files: List of all changed file paths.
        config: Pipeline configuration.

    Returns:
        EngReviewResult with findings, risk summary, and verdict.
    """
    logger.info("[ENG_REVIEW] Senior engineer review on full diff")

    conventions = get_conventions_header(Path(config.cwd))
    mechanical_scores = score_risk(full_diff, changed_files)

    agent_config = make_eng_review_agent(
        conventions=conventions,
        diff=full_diff,
        changed_files=changed_files,
        mechanical_scores=mechanical_scores,
    )

    result = await _run_query(
        prompt=agent_config["prompt"],
        tools=agent_config["tools"],
        model=agent_config["model"],
        cwd=config.cwd,
    )

    findings = _parse_review_findings(result.output)
    risk_summary = _parse_field(result.output, "risk_summary") or ""
    verdict = _parse_field(result.output, "verdict") or "APPROVE"

    logger.info("[ENG_REVIEW] Verdict: %s, %d findings", verdict, len(findings))

    return EngReviewResult(
        findings=findings,
        risk_summary=risk_summary,
        verdict=verdict,
        cost_usd=result.cost_usd,
    )


def run_final_review_static(
    config: PipelineConfig,
) -> StaticReviewResult:
    """Execute static-only FINAL_REVIEW — static checks + /review CLI.

    Args:
        config: Pipeline configuration.

    Returns:
        StaticReviewResult with findings, verdict, and summary.
    """
    logger.info("[FINAL_REVIEW] Running static checks + /review")

    diff_proc = subprocess.run(
        ["git", "diff", "--name-only", config.base_branch],
        capture_output=True,
        text=True,
        cwd=config.cwd,
    )
    changed_files = [f.strip() for f in diff_proc.stdout.strip().splitlines() if f.strip()]

    static_violations = check_files(changed_files, config.cwd)
    static_summary = f"{len(static_violations)} static check violations"
    if static_violations:
        static_details = "\n".join(
            f"  {v.file}:{v.line} [{v.rule}] {v.message}"
            for v in static_violations
        )
        logger.info("[FINAL_REVIEW] Static checks:\n%s", static_details)

    review_context = ""
    if static_violations:
        review_context = "Static check findings (already flagged — focus on contextual issues):\n"
        review_context += "\n".join(f"- {v.rule}: {v.message} ({v.file}:{v.line})" for v in static_violations)

    prompt = f"Run /review on the current branch diff against {config.base_branch}."
    if review_context:
        prompt += f" Additional context: {review_context}"

    review_proc = subprocess.run(
        ["claude", "--print", "--allowedTools", "Read,Glob,Grep", "-p", prompt],
        capture_output=True,
        text=True,
        cwd=config.cwd,
        timeout=300,
    )

    review_output = review_proc.stdout
    verdict = "APPROVE"
    if "BLOCK" in review_output.upper():
        verdict = "BLOCK"
    elif "WARNING" in review_output.upper():
        verdict = "WARNING"

    summary = f"{static_summary}. Review verdict: {verdict}"
    logger.info("[FINAL_REVIEW] %s", summary)

    return StaticReviewResult(
        findings=[{"static_violations": len(static_violations)}],
        verdict=verdict,
        summary=summary,
    )


async def run_final_review(
    config: PipelineConfig,
) -> StaticReviewResult | EngReviewResult:
    """Execute the FINAL_REVIEW phase based on review_mode.

    Args:
        config: Pipeline configuration.

    Returns:
        StaticReviewResult or EngReviewResult depending on review_mode.
    """
    diff_proc = subprocess.run(
        ["git", "diff", config.base_branch],
        capture_output=True,
        text=True,
        cwd=config.cwd,
    )
    full_diff = diff_proc.stdout

    name_proc = subprocess.run(
        ["git", "diff", "--name-only", config.base_branch],
        capture_output=True,
        text=True,
        cwd=config.cwd,
    )
    changed_files = [f.strip() for f in name_proc.stdout.strip().splitlines() if f.strip()]

    if config.review_mode == "static":
        return run_final_review_static(config)

    if config.review_mode == "agent":
        return await run_eng_review(full_diff, changed_files, config)

    # "full" mode — run both static checks and LLM eng-review
    static_result = run_final_review_static(config)
    eng_result = await run_eng_review(full_diff, changed_files, config)

    # Log both results
    logger.info(
        "[FINAL_REVIEW] Full mode — static: %s, eng: %s",
        static_result.verdict,
        eng_result.verdict,
    )

    return eng_result


def run_quality_gates(
    gate_name: str,
    config: PipelineConfig,
) -> bool:
    """Run quality gate hook commands.

    Args:
        gate_name: Gate point name (e.g. "post-verify", "post-review", "pre-commit").
        config: Pipeline configuration.

    Returns:
        True if all gate commands pass (or no gates configured).
    """
    if not config.quality_gates:
        return True

    for cmd in config.quality_gates:
        logger.info("[QUALITY_GATE] %s: running %s", gate_name, cmd)
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=config.cwd,
        )
        if proc.returncode != 0:
            logger.error(
                "[QUALITY_GATE] %s: FAILED — %s\n%s",
                gate_name,
                cmd,
                proc.stderr or proc.stdout,
            )
            return False

    return True


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


def _parse_review_findings(output: str) -> list[ReviewFinding]:
    """Parse review findings from agent output.

    Attempts to extract a JSON block from the output. Falls back to
    an empty list if no valid JSON is found.

    Args:
        output: Agent output text (may contain JSON embedded in markdown).

    Returns:
        List of ReviewFinding objects.
    """
    json_data = _extract_json(output)
    if not json_data:
        return []

    raw_findings = json_data.get("findings", [])
    findings: list[ReviewFinding] = []
    for f in raw_findings:
        if isinstance(f, dict):
            findings.append(ReviewFinding(
                severity=f.get("severity", ""),
                file=f.get("file", ""),
                line=f.get("line"),
                title=f.get("title", ""),
                detail=f.get("why", f.get("detail", "")),
            ))
    return findings


def _parse_field(output: str, field: str) -> str | None:
    """Extract a string field from JSON in agent output.

    Args:
        output: Agent output text.
        field: JSON field name to extract.

    Returns:
        The field value as a string, or None if not found.
    """
    json_data = _extract_json(output)
    if not json_data:
        return None
    value = json_data.get(field)
    return str(value) if value is not None else None


def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from text.

    Looks for JSON inside code fences first, then tries the raw text.

    Args:
        text: Text that may contain a JSON object.

    Returns:
        Parsed dict, or None if no valid JSON found.
    """
    # Try to find JSON in code fences
    fence_match = re.search(r"```(?:json)?\s*\n(\{.*?\})\s*\n```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a raw JSON object
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None

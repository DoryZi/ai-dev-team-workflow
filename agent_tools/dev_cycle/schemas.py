from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImplementResult:
    """Result of the IMPLEMENT phase — single agent writes code and tests.

    Combines what RED and GREEN used to produce separately: both test files
    and production code changes in one session.

    Attributes:
        test_files: Paths to test files created or modified.
        changed_files: Paths to production files created or modified.
        cost_usd: Agent SDK cost for this phase.
        agent_output: Full agent text output for vault persistence.
    """

    test_files: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    agent_output: str = ""


@dataclass
class VerifyResult:
    """Result of the VERIFY phase — pytest execution.

    Attributes:
        passed: Whether all tests passed.
        num_tests: Total number of tests discovered.
        num_failures: Number of failing tests.
        failures: List of failure descriptions (test name + short reason).
    """

    passed: bool = False
    num_tests: int = 0
    num_failures: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass
class ExploreResult:
    """Result of the EXPLORE phase — codebase exploration.

    Attributes:
        context: Markdown text with exploration findings.
        cost_usd: Agent SDK cost for this phase.
        saved_path: Path where exploration was saved, or None.
    """

    context: str = ""
    cost_usd: float = 0.0
    saved_path: str | None = None


@dataclass
class ReviewFinding:
    """A single finding from an LLM review agent.

    Attributes:
        severity: CRITICAL, HIGH, MEDIUM, or LOW.
        file: File path where the issue was found.
        line: Line number, or None if file-wide.
        title: Short description of the issue.
        detail: Explanation and suggested fix.
    """

    severity: str = ""
    file: str = ""
    line: int | None = None
    title: str = ""
    detail: str = ""


@dataclass
class AgentReviewResult:
    """Result of per-step LLM convention review.

    Attributes:
        findings: List of review findings.
        has_critical_or_high: Whether any CRITICAL or HIGH findings exist.
        cost_usd: Agent SDK cost for this phase.
    """

    findings: list[ReviewFinding] = field(default_factory=list)
    has_critical_or_high: bool = False
    cost_usd: float = 0.0


@dataclass
class EngReviewResult:
    """Result of final LLM engineering review.

    Attributes:
        findings: List of review findings.
        risk_summary: Free-form risk assessment from the LLM.
        verdict: APPROVE, APPROVE_WITH_FIXES, or REQUEST_CHANGES.
        cost_usd: Agent SDK cost for this phase.
    """

    findings: list[ReviewFinding] = field(default_factory=list)
    risk_summary: str = ""
    verdict: str = ""
    cost_usd: float = 0.0


@dataclass
class StaticReviewResult:
    """Result of the static-only FINAL_REVIEW phase.

    Attributes:
        findings: List of review finding dicts from /review.
        verdict: Review verdict (APPROVE, WARNING, BLOCK).
        summary: Human-readable summary of review results.
    """

    findings: list[dict] = field(default_factory=list)
    verdict: str = ""
    summary: str = ""


@dataclass
class StepResult:
    """Result of executing a single plan step through the pipeline.

    Attributes:
        step_number: The step number from the plan.
        title: The step title from the plan.
        implement: Result of the IMPLEMENT phase, or None if not run.
        verify: Result of the VERIFY phase (lint + pytest), or None if not run.
        review: Result of the REVIEW phase, or None if not run.
        committed: Whether the step was committed to git.
        attempts: Number of verify retry attempts used.
        cost_usd: Total agent SDK cost for this step.
    """

    step_number: int = 0
    title: str = ""
    implement: ImplementResult | None = None
    verify: VerifyResult | None = None
    review: AgentReviewResult | None = None
    committed: bool = False
    attempts: int = 0
    cost_usd: float = 0.0


@dataclass
class PipelineResult:
    """Result of a full pipeline run.

    Attributes:
        status: Overall status — "success" or "failed".
        steps: Results for each step executed.
        final_review: Result of the final review, or None if not reached.
        total_cost_usd: Total agent SDK cost across all steps.
        failure_detail: Description of what failed, if status is "failed".
        pr_url: URL of the created PR, if applicable.
    """

    status: str = "failed"
    steps: list[StepResult] = field(default_factory=list)
    explore: ExploreResult | None = None
    final_review: StaticReviewResult | EngReviewResult | None = None
    total_cost_usd: float = 0.0
    failure_detail: str | None = None
    pr_url: str | None = None

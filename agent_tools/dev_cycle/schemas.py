from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RedResult:
    """Result of the RED phase — test-eng writes failing tests.

    Attributes:
        test_files: Paths to test files created by test-eng.
        cost_usd: Agent SDK cost for this phase.
    """

    test_files: list[str] = field(default_factory=list)
    cost_usd: float = 0.0


@dataclass
class GreenResult:
    """Result of the GREEN phase — SDE implements production code.

    Attributes:
        changed_files: Paths to files created or modified by SDE.
        cost_usd: Agent SDK cost for this phase.
    """

    changed_files: list[str] = field(default_factory=list)
    cost_usd: float = 0.0


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
class LintResult:
    """Result of the LINT phase — ruff format + ruff check.

    Attributes:
        passed: Whether lint checks passed (no violations).
        violations: List of lint violation descriptions.
    """

    passed: bool = False
    violations: list[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """Result of the FINAL_REVIEW phase — static checks + /review.

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
        red: Result of the RED phase, or None if not run.
        green: Result of the GREEN phase, or None if not run.
        verify: Result of the VERIFY phase, or None if not run.
        lint: Result of the LINT phase, or None if not run.
        committed: Whether the step was committed to git.
        attempts: Number of verify retry attempts used.
        cost_usd: Total agent SDK cost for this step.
    """

    step_number: int = 0
    title: str = ""
    red: RedResult | None = None
    green: GreenResult | None = None
    verify: VerifyResult | None = None
    lint: LintResult | None = None
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
    final_review: ReviewResult | None = None
    total_cost_usd: float = 0.0
    failure_detail: str | None = None
    pr_url: str | None = None

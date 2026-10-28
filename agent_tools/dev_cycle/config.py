from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineConfig:
    """Configuration for a dev-cycle pipeline run.

    Controls which steps to execute, retry limits, review mode,
    and behavioral flags for the pipeline orchestrator.

    Attributes:
        plan_path: Absolute path to the plan markdown file.
        step: Specific step number to execute, or None for all steps.
        phase: Specific phase to run, or None for the full loop.
        max_verify_attempts: Max retries for VERIFY (lint + pytest) per step.
        max_review_iterations: Max REVIEW→IMPLEMENT retry cycles per step.
        review_mode: Review depth — "static", "agent", or "full".
        skip_explore: Skip the codebase exploration phase.
        quality_gates: Shell commands to run at gate points.
        parallel: Run independent steps concurrently within groups.
        base_branch: Git branch to base the PR on.
        cwd: Repository root directory.
        dry_run: Validate plan structure only, don't execute.
    """

    plan_path: str
    step: int | None = None
    phase: str | None = None
    max_verify_attempts: int = 3
    max_review_iterations: int = 2
    review_mode: str = "static"
    skip_explore: bool = False
    quality_gates: list[str] = field(default_factory=list)
    parallel: bool = False
    use_oauth: bool = False
    base_branch: str = "main"
    cwd: str = "."
    dry_run: bool = False

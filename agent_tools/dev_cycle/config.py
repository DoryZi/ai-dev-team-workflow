from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineConfig:
    """Configuration for a TDD dev-cycle pipeline run.

    Controls which steps to execute, retry limits, and behavioral
    flags for the pipeline orchestrator.

    Attributes:
        plan_path: Absolute path to the plan markdown file.
        step: Specific step number to execute, or None for all steps.
        phase: Specific phase to run, or None for the full loop.
        max_verify_attempts: Max retries for the verify phase per step.
        max_lint_attempts: Max retries for lint/format fixes per step.
        base_branch: Git branch to base the PR on.
        cwd: Repository root directory.
        dry_run: Validate plan structure only, don't execute.
    """

    plan_path: str
    step: int | None = None
    phase: str | None = None
    max_verify_attempts: int = 3
    max_lint_attempts: int = 3
    base_branch: str = "main"
    cwd: str = "."
    dry_run: bool = False

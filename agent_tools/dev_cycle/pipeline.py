"""Full pipeline orchestrator for the TDD dev-cycle.

Parses a plan file, then executes each step through the state machine:
[EXPLORE] → RED → GREEN → VERIFY → LINT → [REVIEW] → COMMIT.
After all steps, runs the final review before PR creation.

The EXPLORE and REVIEW phases are controlled by config flags.

Usage:
    from pipeline import run_pipeline
    result = asyncio.run(run_pipeline(config))
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from config import PipelineConfig
from plan_parser import parse_plan
from schemas import (
    PipelineResult,
    StepResult,
)
from state_machine import Phase
from steps import (
    run_explore,
    run_final_review,
    run_green,
    run_green_fix,
    run_lint,
    run_quality_gates,
    run_red,
    run_review,
    run_verify,
)

logger = logging.getLogger(__name__)


async def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the full TDD dev-cycle pipeline.

    Parses the plan, then for each step runs:
    RED → GREEN → VERIFY (retry loop) → LINT (retry loop) → COMMIT.
    After all steps complete, runs the final review.

    Args:
        config: Pipeline configuration (plan path, limits, flags).

    Returns:
        PipelineResult with per-step results and overall status.
    """
    plan = parse_plan(Path(config.plan_path))

    if config.dry_run:
        logger.info("Dry run — plan validated: %d steps", len(plan.steps))
        return PipelineResult(
            status="success",
            failure_detail="Dry run — plan validated only.",
        )

    # Determine which steps to run
    steps_to_run = plan.steps
    if config.step is not None:
        steps_to_run = [s for s in plan.steps if s.number >= config.step]
        if not steps_to_run:
            return PipelineResult(
                status="failed",
                failure_detail=f"Step {config.step} not found in plan.",
            )

    result = PipelineResult(status="success")
    prior_files: list[str] = []
    explore_context = ""

    # --- EXPLORE phase (runs once before all steps) ---
    if not config.skip_explore:
        logger.info("=" * 60)
        logger.info("EXPLORE — Codebase research")
        logger.info("=" * 60)
        try:
            explore_result = await run_explore(plan=plan, config=config)
            result.explore = explore_result
            result.total_cost_usd += explore_result.cost_usd
            explore_context = explore_result.context
        except Exception as exc:
            logger.warning("Explore phase failed (non-fatal): %s", exc)

    # Collect prior files from steps before the starting step
    if config.step is not None:
        for s in plan.steps:
            if s.number < config.step:
                prior_files.extend(s.files)

    for step in steps_to_run:
        logger.info("=" * 60)
        logger.info("Step %d/%d: %s", step.number, len(plan.steps), step.title)
        logger.info("=" * 60)

        step_result = StepResult(
            step_number=step.number,
            title=step.title,
        )

        try:
            step_result = await _run_step(
                step_result=step_result,
                step=step,
                plan_text=plan.raw_text,
                prior_files=prior_files,
                config=config,
                explore_context=explore_context,
            )
        except Exception as exc:
            logger.error("Step %d failed with exception: %s", step.number, exc)
            step_result.committed = False
            result.steps.append(step_result)
            result.status = "failed"
            result.failure_detail = f"Step {step.number} ({step.title}): {exc}"
            break

        result.steps.append(step_result)
        result.total_cost_usd += step_result.cost_usd

        # Check if step completed successfully
        if not step_result.committed:
            result.status = "failed"
            result.failure_detail = f"Step {step.number} ({step.title}) did not complete."
            break

        # Track files for subsequent steps
        prior_files.extend(step.files)
        if step_result.green:
            prior_files.extend(step_result.green.changed_files)

    # Final review — only if all steps succeeded
    if result.status == "success":
        logger.info("=" * 60)
        logger.info("FINAL REVIEW")
        logger.info("=" * 60)

        try:
            result.final_review = await run_final_review(config)
        except Exception as exc:
            logger.error("Final review failed: %s", exc)
            result.final_review = None
            result.failure_detail = f"Final review failed: {exc}"
            # Don't fail the whole pipeline — steps succeeded

    return result


async def _run_step(
    step_result: StepResult,
    step,
    plan_text: str,
    prior_files: list[str],
    config: PipelineConfig,
    explore_context: str = "",
) -> StepResult:
    """Execute a single step through the full phase cycle.

    Args:
        step_result: The StepResult to populate.
        step: The plan step to execute.
        plan_text: Full plan markdown text.
        prior_files: Files from previously completed steps.
        config: Pipeline configuration.
        explore_context: Codebase exploration context from the EXPLORE phase.

    Returns:
        Updated StepResult with phase results.
    """
    # --- RED ---
    logger.info("[Step %d] Phase: RED", step.number)
    step_result.red = await run_red(
        step=step,
        plan_text=plan_text,
        config=config,
        prior_files=prior_files,
        explore_context=explore_context,
    )
    step_result.cost_usd += step_result.red.cost_usd
    test_files = step_result.red.test_files

    # --- GREEN ---
    logger.info("[Step %d] Phase: GREEN", step.number)
    step_result.green = await run_green(
        step=step,
        plan_text=plan_text,
        test_files=test_files,
        config=config,
        prior_files=prior_files,
        explore_context=explore_context,
    )
    step_result.cost_usd += step_result.green.cost_usd

    # --- VERIFY (with retry loop) ---
    test_dir = _find_test_dir(test_files, config.cwd)

    for attempt in range(1, config.max_verify_attempts + 1):
        logger.info("[Step %d] Phase: VERIFY (attempt %d/%d)", step.number, attempt, config.max_verify_attempts)
        step_result.verify = run_verify(test_dir=test_dir, config=config)
        step_result.attempts = attempt

        if step_result.verify.passed:
            break

        # Retry: SDE fixes production code
        if attempt < config.max_verify_attempts:
            logger.info("[Step %d] Tests failed — SDE fixing (attempt %d)", step.number, attempt)
            failure_output = "\n".join(step_result.verify.failures)
            fix_result = await run_green_fix(
                step=step,
                plan_text=plan_text,
                test_files=test_files,
                failure_output=failure_output,
                config=config,
                prior_files=prior_files,
                explore_context=explore_context,
            )
            step_result.cost_usd += fix_result.cost_usd

    if not step_result.verify.passed:
        logger.error("[Step %d] VERIFY failed after %d attempts", step.number, config.max_verify_attempts)
        return step_result

    # --- LINT (with retry loop) ---
    all_changed = step_result.green.changed_files + test_files

    for attempt in range(1, config.max_lint_attempts + 1):
        logger.info("[Step %d] Phase: LINT (attempt %d/%d)", step.number, attempt, config.max_lint_attempts)
        step_result.lint = run_lint(changed_files=all_changed, config=config)

        if step_result.lint.passed:
            break

        # ruff --fix already ran inside run_lint, so just retry the check
        if attempt < config.max_lint_attempts:
            logger.info("[Step %d] Lint issues remain — retrying", step.number)

    # --- Quality gate: post-verify ---
    run_quality_gates("post-verify", config)

    # --- REVIEW (LLM convention review, agent/full modes only) ---
    if config.review_mode in ("agent", "full"):
        diff_proc = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=config.cwd,
        )

        for review_attempt in range(1, config.max_review_iterations + 1):
            logger.info(
                "[Step %d] Phase: REVIEW (attempt %d/%d)",
                step.number, review_attempt, config.max_review_iterations,
            )
            step_result.review = await run_review(
                diff=diff_proc.stdout,
                changed_files=all_changed,
                config=config,
            )
            step_result.cost_usd += step_result.review.cost_usd

            if not step_result.review.has_critical_or_high:
                break

            # SDE fixes based on review findings
            if review_attempt < config.max_review_iterations:
                findings_text = "\n".join(
                    f"- [{f.severity}] {f.file}:{f.line} — {f.title}: {f.detail}"
                    for f in step_result.review.findings
                )
                logger.info("[Step %d] Review found issues — SDE fixing", step.number)
                fix_result = await run_green_fix(
                    step=step,
                    plan_text=plan_text,
                    test_files=test_files,
                    failure_output=f"Review findings:\n{findings_text}",
                    config=config,
                    prior_files=prior_files,
                    explore_context=explore_context,
                )
                step_result.cost_usd += fix_result.cost_usd

                # Re-get diff after fix
                diff_proc = subprocess.run(
                    ["git", "diff", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=config.cwd,
                )

        # Quality gate: post-review
        run_quality_gates("post-review", config)

    # --- Quality gate: pre-commit ---
    run_quality_gates("pre-commit", config)

    # --- COMMIT ---
    logger.info("[Step %d] Phase: COMMIT", step.number)
    step_result.committed = _commit_step(step.number, step.title, config.cwd)

    return step_result


def _find_test_dir(test_files: list[str], cwd: str) -> str:
    """Determine the project directory for running pytest.

    Finds the common parent that contains pyproject.toml.

    Args:
        test_files: List of test file paths.
        cwd: Repository root.

    Returns:
        Directory path suitable for ``uv run --directory``.
    """
    if not test_files:
        return cwd

    # Walk up from the first test file to find pyproject.toml
    first_test = Path(cwd) / test_files[0]
    current = first_test.parent

    while current != Path(cwd).parent:
        if (current / "pyproject.toml").exists():
            return str(current)
        current = current.parent

    return cwd


def _commit_step(step_number: int, title: str, cwd: str) -> bool:
    """Git add and commit the step's changes.

    Args:
        step_number: Step number for the commit message.
        title: Step title for the commit message.
        cwd: Repository root.

    Returns:
        True if the commit succeeded.
    """
    subprocess.run(
        ["git", "add", "-A"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    commit_msg = f"Step {step_number}: {title}"
    commit_proc = subprocess.run(
        ["git", "commit", "-m", commit_msg, "--allow-empty"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if commit_proc.returncode == 0:
        logger.info("Committed: %s", commit_msg)
        return True

    logger.warning("Commit failed: %s", commit_proc.stderr.strip())
    return False

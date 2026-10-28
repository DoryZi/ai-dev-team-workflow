"""Full pipeline orchestrator for the dev-cycle.

Parses a plan file, then executes each step through the state machine:
[EXPLORE] → IMPLEMENT → VERIFY → [REVIEW] → COMMIT.
After all steps, runs the final review before PR creation.

VERIFY includes lint (ruff) and full-suite pytest in one phase.
REVIEW loops back to IMPLEMENT if CRITICAL/HIGH findings exist.

Usage:
    from pipeline import run_pipeline
    result = asyncio.run(run_pipeline(config))
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from config import PipelineConfig
from plan_parser import Plan, PlanStep, get_parallel_groups, parse_plan
from schemas import (
    AgentReviewResult,
    PipelineResult,
    StepResult,
)
from state_machine import Phase
from steps import (
    run_arch_review,
    run_explore,
    run_final_review,
    run_implement,
    run_implement_fix,
    run_quality_gates,
    run_review,
    run_test_review,
    run_verify,
    set_use_oauth,
)
from vault import load_context_for_step, save_run_summary, save_step_note, start_run

logger = logging.getLogger(__name__)


async def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the full TDD dev-cycle pipeline.

    Parses the plan, then for each step runs:
    IMPLEMENT → VERIFY (lint + pytest) → REVIEW → COMMIT.
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

    # --- Configure OAuth mode ---
    if config.use_oauth:
        set_use_oauth(True)
        logger.info("OAuth mode enabled — using Max subscription instead of API credits")

    # --- Start vault run ---
    vault_manifest = start_run(config.plan_path)

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

    # Build list of completed prior steps for context truncation
    prior_steps: list[PlanStep] = []
    if config.step is not None:
        prior_steps = [s for s in plan.steps if s.number < config.step]

    if config.parallel:
        groups = get_parallel_groups(steps_to_run)
    else:
        groups = [[s] for s in steps_to_run]

    for group in groups:
        if len(group) == 1:
            # Sequential execution for single-step groups
            step = group[0]
            logger.info("=" * 60)
            logger.info("Step %d/%d: %s", step.number, len(plan.steps), step.title)
            logger.info("=" * 60)

            step_result = await _run_single_step(
                step=step,
                plan=plan,
                prior_files=prior_files,
                prior_steps=prior_steps,
                config=config,
                explore_context=explore_context,
                vault_manifest=vault_manifest,
            )

            result.steps.append(step_result)
            result.total_cost_usd += step_result.cost_usd

            if not step_result.committed:
                result.status = "failed"
                result.failure_detail = f"Step {step.number} ({step.title}) did not complete."
                break

            prior_files.extend(step.files)
            if step_result.implement:
                prior_files.extend(step_result.implement.changed_files)
                prior_files.extend(step_result.implement.test_files)
            elif step_result.green:
                prior_files.extend(step_result.green.changed_files)
            prior_steps.append(step)

        else:
            # Parallel execution for multi-step groups
            logger.info("=" * 60)
            logger.info(
                "Parallel group: steps %s",
                ", ".join(str(s.number) for s in group),
            )
            logger.info("=" * 60)

            coros = [
                _run_single_step(
                    step=step,
                    plan=plan,
                    prior_files=list(prior_files),
                    prior_steps=list(prior_steps),
                    config=config,
                    explore_context=explore_context,
                    vault_manifest=vault_manifest,
                )
                for step in group
            ]
            group_results = await asyncio.gather(*coros, return_exceptions=True)

            group_failed = False
            for step, step_result in zip(group, group_results):
                if isinstance(step_result, Exception):
                    logger.error("Step %d failed: %s", step.number, step_result)
                    sr = StepResult(step_number=step.number, title=step.title)
                    sr.committed = False
                    result.steps.append(sr)
                    result.status = "failed"
                    result.failure_detail = f"Step {step.number} ({step.title}): {step_result}"
                    group_failed = True
                else:
                    result.steps.append(step_result)
                    result.total_cost_usd += step_result.cost_usd
                    if not step_result.committed:
                        result.status = "failed"
                        result.failure_detail = f"Step {step.number} ({step.title}) did not complete."
                        group_failed = True

            # Commit each step individually after group completes
            # (commits already happen inside _run_step)

            # Accumulate prior files from all steps in the group
            for step in group:
                prior_files.extend(step.files)
            for step_result_item in result.steps[-len(group):]:
                if isinstance(step_result_item, Exception):
                    continue
                if step_result_item.implement:
                    prior_files.extend(step_result_item.implement.changed_files)
                    prior_files.extend(step_result_item.implement.test_files)
                elif step_result_item.green:
                    prior_files.extend(step_result_item.green.changed_files)
            prior_steps.extend(group)

            if group_failed:
                break

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

    # --- Save vault run summary ---
    try:
        save_run_summary(
            manifest=vault_manifest,
            total_cost_usd=result.total_cost_usd,
            status=result.status,
            failure_detail=result.failure_detail,
        )
    except Exception as exc:
        logger.warning("Failed to save vault run summary: %s", exc)

    return result


async def _run_single_step(
    step: PlanStep,
    plan: Plan,
    prior_files: list[str],
    prior_steps: list[PlanStep],
    config: PipelineConfig,
    explore_context: str = "",
    vault_manifest=None,
) -> StepResult:
    """Create a StepResult and delegate to _run_step.

    Convenience wrapper that builds the StepResult and catches exceptions.

    Args:
        step: The plan step to execute.
        plan: Parsed plan object.
        prior_files: Files from previously completed steps.
        prior_steps: Completed steps for context truncation.
        config: Pipeline configuration.
        explore_context: Codebase exploration context from EXPLORE phase.
        vault_manifest: Vault run manifest for context persistence.

    Returns:
        StepResult with phase results.
    """
    step_result = StepResult(step_number=step.number, title=step.title)
    try:
        step_result = await _run_step(
            step_result=step_result,
            step=step,
            plan_text=plan.raw_text,
            prior_files=prior_files,
            prior_steps=prior_steps,
            config=config,
            explore_context=explore_context,
            vault_manifest=vault_manifest,
        )
    except Exception as exc:
        logger.error("Step %d failed with exception: %s", step.number, exc)
        step_result.committed = False
    return step_result


def _build_state_snapshot(cwd: str) -> str:
    """Build a snapshot of the project's current file tree.

    Gives agents awareness of what files exist so they don't write
    imports for missing modules or duplicate existing work.

    Args:
        cwd: Repository root directory.

    Returns:
        Markdown-formatted file tree summary.
    """
    cwd_path = Path(cwd)
    py_files = sorted(
        str(p.relative_to(cwd_path))
        for p in cwd_path.rglob("*.py")
        if ".venv" not in p.parts and "__pycache__" not in p.parts
    )
    toml_files = sorted(
        str(p.relative_to(cwd_path))
        for p in cwd_path.rglob("pyproject.toml")
        if ".venv" not in p.parts
    )
    other_files = sorted(
        str(p.relative_to(cwd_path))
        for p in cwd_path.rglob("*")
        if p.is_file()
        and ".venv" not in p.parts
        and "__pycache__" not in p.parts
        and p.suffix in {".html", ".css", ".js", ".md", ".toml", ".yaml", ".yml"}
        and p.suffix != ".py"
    )

    all_files = toml_files + py_files + other_files
    if not all_files:
        return "## Current Project State\n\nNo files found yet."

    tree = "\n".join(f"- {f}" for f in all_files[:100])
    return f"## Current Project State ({len(all_files)} files)\n\n{tree}"


def _read_test_contents(test_files: list[str], cwd: str) -> str:
    """Read test file contents to pass directly to GREEN agent.

    Instead of just file paths, GREEN gets the actual test code so it
    knows exactly what to implement without needing to read files first.

    Args:
        test_files: List of test file paths (relative to cwd).
        cwd: Repository root directory.

    Returns:
        Markdown-formatted test file contents.
    """
    if not test_files:
        return ""

    cwd_path = Path(cwd)
    sections: list[str] = []

    for tf in test_files:
        path = cwd_path / tf
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                sections.append(f"### {tf}\n\n```python\n{content}\n```")
            except OSError:
                sections.append(f"### {tf}\n\n(could not read)")

    # Also find test files not in the list (written by RED but not detected)
    for test_path in sorted(cwd_path.rglob("test_*.py")):
        if ".venv" not in test_path.parts and "__pycache__" not in test_path.parts:
            rel = str(test_path.relative_to(cwd_path))
            if rel not in test_files:
                try:
                    content = test_path.read_text(encoding="utf-8")
                    sections.append(f"### {rel} (discovered)\n\n```python\n{content}\n```")
                except OSError:
                    pass

    if not sections:
        return ""

    return "## Test Files (your implementation spec)\n\n" + "\n\n".join(sections)


async def _run_step(
    step_result: StepResult,
    step: PlanStep,
    plan_text: str,
    prior_files: list[str],
    prior_steps: list[PlanStep],
    config: PipelineConfig,
    explore_context: str = "",
    vault_manifest=None,
) -> StepResult:
    """Execute a single step through the phase cycle.

    Flow: IMPLEMENT → VERIFY → REVIEW → COMMIT.
    VERIFY includes lint (ruff) and full-suite pytest.
    REVIEW loops back to IMPLEMENT if CRITICAL/HIGH findings exist.

    Args:
        step_result: The StepResult to populate.
        step: The plan step to execute.
        plan_text: Full plan markdown text.
        prior_files: Files from previously completed steps.
        prior_steps: Completed steps for context truncation.
        config: Pipeline configuration.
        explore_context: Codebase exploration context from the EXPLORE phase.
        vault_manifest: Vault run manifest for context persistence.

    Returns:
        Updated StepResult with phase results.
    """
    # --- Load vault context ---
    vault_context = ""
    if vault_manifest:
        try:
            vault_context = load_context_for_step(
                plan_path=config.plan_path,
                current_manifest=vault_manifest,
                step_number=step.number,
            )
            if vault_context:
                logger.info("[Step %d] Loaded vault context (%d chars)", step.number, len(vault_context))
        except Exception as exc:
            logger.warning("[Step %d] Failed to load vault context: %s", step.number, exc)

    # --- Build state snapshot ---
    build_state = _build_state_snapshot(config.cwd)

    # Track fix agent outputs for vault persistence
    fix_outputs: list[str] = []

    # --- IMPLEMENT ---
    logger.info("[Step %d] Phase: IMPLEMENT", step.number)
    step_result.implement = await run_implement(
        step=step,
        plan_text=plan_text,
        config=config,
        prior_files=prior_files,
        explore_context=explore_context,
        prior_steps=prior_steps,
        vault_context=vault_context,
        build_state=build_state,
    )
    step_result.cost_usd += step_result.implement.cost_usd
    test_files = step_result.implement.test_files
    all_changed = step_result.implement.changed_files + test_files

    # --- VERIFY (lint + full-suite pytest) ---
    test_dir = _find_test_dir(test_files, config.cwd, step_files=step.files)

    for attempt in range(1, config.max_verify_attempts + 1):
        logger.info("[Step %d] Phase: VERIFY (attempt %d/%d)", step.number, attempt, config.max_verify_attempts)
        step_result.verify = run_verify(
            test_dir=test_dir, config=config, changed_files=all_changed,
        )
        step_result.attempts = attempt

        if step_result.verify.passed:
            break

        if attempt < config.max_verify_attempts:
            logger.info("[Step %d] Verify failed — fixing (attempt %d)", step.number, attempt)
            failure_output = "\n".join(step_result.verify.failures)
            fix_state = _build_state_snapshot(config.cwd)
            failure_output = f"{fix_state}\n\n## Failures\n\n{failure_output}"
            fix_result = await run_implement_fix(
                step=step,
                plan_text=plan_text,
                failure_output=failure_output,
                config=config,
                prior_files=prior_files,
                explore_context=explore_context,
                prior_steps=prior_steps,
                vault_context=vault_context,
                build_state=fix_state,
            )
            step_result.cost_usd += fix_result.cost_usd
            fix_outputs.append(fix_result.agent_output)

    if not step_result.verify.passed:
        logger.error("[Step %d] VERIFY failed after %d attempts", step.number, config.max_verify_attempts)
        return step_result

    run_quality_gates("post-verify", config)

    # --- REVIEW (loops back to IMPLEMENT if CRITICAL/HIGH) ---
    if config.review_mode in ("agent", "full"):
        for review_attempt in range(1, config.max_review_iterations + 1):
            diff_proc = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                text=True,
                cwd=config.cwd,
            )

            logger.info(
                "[Step %d] Phase: REVIEW (attempt %d/%d)",
                step.number, review_attempt, config.max_review_iterations,
            )

            test_review_coro = run_test_review(
                diff=diff_proc.stdout,
                changed_files=all_changed,
                config=config,
                step=step,
            )
            arch_review_coro = run_arch_review(
                diff=diff_proc.stdout,
                changed_files=all_changed,
                config=config,
                step=step,
            )

            test_review_result, arch_review_result = await asyncio.gather(
                test_review_coro, arch_review_coro,
            )

            all_findings = test_review_result.findings + arch_review_result.findings
            has_critical_or_high = (
                test_review_result.has_critical_or_high
                or arch_review_result.has_critical_or_high
            )
            review_cost = test_review_result.cost_usd + arch_review_result.cost_usd

            step_result.review = AgentReviewResult(
                findings=all_findings,
                has_critical_or_high=has_critical_or_high,
                cost_usd=review_cost,
            )
            step_result.cost_usd += review_cost

            if not has_critical_or_high:
                break

            # Loop back to IMPLEMENT with review findings
            if review_attempt < config.max_review_iterations:
                findings_text = "\n".join(
                    f"- [{f.severity}] {f.file}:{f.line} — {f.title}: {f.detail}"
                    for f in all_findings
                )
                logger.info("[Step %d] Review found issues — re-running IMPLEMENT", step.number)
                fix_state = _build_state_snapshot(config.cwd)
                fix_result = await run_implement_fix(
                    step=step,
                    plan_text=plan_text,
                    failure_output=f"## Review Findings\n\n{findings_text}",
                    config=config,
                    prior_files=prior_files,
                    explore_context=explore_context,
                    prior_steps=prior_steps,
                    vault_context=vault_context,
                    build_state=fix_state,
                )
                step_result.cost_usd += fix_result.cost_usd
                fix_outputs.append(fix_result.agent_output)

                # Re-verify after IMPLEMENT fix
                step_result.verify = run_verify(
                    test_dir=test_dir, config=config, changed_files=all_changed,
                )
                if not step_result.verify.passed:
                    logger.error("[Step %d] VERIFY failed after review fix", step.number)
                    return step_result

        run_quality_gates("post-review", config)

    run_quality_gates("pre-commit", config)

    # --- COMMIT ---
    logger.info("[Step %d] Phase: COMMIT", step.number)
    step_result.committed = _commit_step(step.number, step.title, config.cwd)

    # --- Save vault note ---
    if vault_manifest:
        try:
            implement_output = step_result.implement.agent_output if step_result.implement else ""
            save_step_note(
                manifest=vault_manifest,
                step_result=step_result,
                cwd=config.cwd,
                implement_output=implement_output,
                fix_outputs=fix_outputs,
            )
        except Exception as exc:
            logger.warning("[Step %d] Failed to save vault note: %s", step.number, exc)

    return step_result


def _find_test_dir(
    test_files: list[str],
    cwd: str,
    step_files: list[str] | None = None,
) -> str:
    """Determine the project directory for running pytest.

    Tries multiple strategies in order:
    1. Walk up from the first test file to find pyproject.toml.
    2. Walk up from step_files to find pyproject.toml.
    3. Glob for any pyproject.toml under cwd with a sibling tests/ dir.
    4. Fall back to cwd.

    Args:
        test_files: List of test file paths from RED phase output.
        cwd: Repository root.
        step_files: File paths from the plan step (optional fallback).

    Returns:
        Directory path suitable for ``uv run --directory``.
    """
    cwd_path = Path(cwd)

    # Strategy 1: Walk up from test files
    if test_files:
        first_test = cwd_path / test_files[0]
        current = first_test.parent
        while current != cwd_path.parent:
            if (current / "pyproject.toml").exists():
                return str(current)
            current = current.parent

    # Strategy 2: Walk up from step files
    if step_files:
        for f in step_files:
            full = cwd_path / f
            current = full.parent
            while current != cwd_path.parent:
                if (current / "pyproject.toml").exists():
                    return str(current)
                current = current.parent

    # Strategy 3: Glob for pyproject.toml with sibling tests/
    for toml in sorted(cwd_path.rglob("pyproject.toml")):
        if ".venv" in toml.parts:
            continue
        if (toml.parent / "tests").is_dir():
            return str(toml.parent)

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

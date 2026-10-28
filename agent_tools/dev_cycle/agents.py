"""Agent configuration builders for the dev-cycle pipeline.

Constructs prompt + tools + model dicts for each agent role. Each builder
loads a base prompt from the prompts/ directory, then appends role-specific
context (plan, test files, conventions, diffs, etc.).
"""
from __future__ import annotations

import logging
from pathlib import Path

from plan_parser import PlanStep

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Tool sets per agent role.
_SDE_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
_TEST_ENG_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
_REVIEW_TOOLS = ["Read", "Glob", "Grep"]
_EXPLORE_TOOLS = ["Read", "Glob", "Grep"]

_MODEL = "claude-opus-4-20250514"


def truncate_plan_for_step(
    plan_text: str,
    step: PlanStep,
    prior_steps: list[PlanStep],
) -> str:
    """Build a reduced plan context for a single step.

    Returns only the acceptance criteria section, the current step's full
    section, and prior steps summarized as titles + file lists.

    Args:
        plan_text: Full plan markdown text.
        step: The current step being executed.
        prior_steps: Steps that have already been completed.

    Returns:
        Trimmed plan text with only relevant sections.
    """
    import re as _re

    parts: list[str] = []

    # 0. Extract project goal (title + context before first ## section)
    goal_match = _re.match(
        r"(^#\s+.+?\n.*?)(?=^##\s)",
        plan_text,
        _re.MULTILINE | _re.DOTALL,
    )
    if goal_match:
        goal_text = goal_match.group(1).strip()
        # Cap at ~500 chars to keep context lean
        if len(goal_text) > 500:
            goal_text = goal_text[:500] + "..."
        parts.append(goal_text)

    # 1. Extract acceptance criteria section
    ac_match = _re.search(
        r"(^##\s+Acceptance\s+Criteria\b.*?\n.*?)(?=^##\s|\Z)",
        plan_text,
        _re.MULTILINE | _re.DOTALL | _re.IGNORECASE,
    )
    if ac_match:
        parts.append(ac_match.group(1).strip())

    # 2. Summarize prior steps (title + files only)
    if prior_steps:
        parts.append("## Prior Steps (completed)")
        for ps in prior_steps:
            files_str = ", ".join(ps.files) if ps.files else "(no files)"
            parts.append(f"- Step {ps.number}: {ps.title} — files: {files_str}")

    # 3. Extract the current step's full section from the plan
    step_header_re = _re.compile(
        rf"^##\s+Step\s+{step.number}\s*[:\-\u2014\u2013]\s*.+$",
        _re.MULTILINE,
    )
    step_match = step_header_re.search(plan_text)
    if step_match:
        # Find where the next step header starts (or end of text)
        next_step_re = _re.compile(
            r"^##\s+Step\s+\d+\s*[:\-\u2014\u2013]",
            _re.MULTILINE,
        )
        rest = plan_text[step_match.end():]
        next_match = next_step_re.search(rest)
        end_pos = step_match.end() + next_match.start() if next_match else len(plan_text)
        parts.append(plan_text[step_match.start():end_pos].strip())
    else:
        # Fallback: include the step description directly
        parts.append(f"## Step {step.number} — {step.title}\n\n{step.description}")

    return "\n\n".join(parts)


def _load_prompt(name: str) -> str:
    """Load a prompt markdown file from the prompts directory.

    Args:
        name: Prompt file name without extension (e.g. "sde", "test_eng").

    Returns:
        The prompt text.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def make_implement_agent(
    step: PlanStep,
    conventions: str,
    plan_text: str,
    prior_files: list[str],
    extra_context: str = "",
    explore_context: str = "",
    prior_steps: list[PlanStep] | None = None,
    vault_context: str = "",
    build_state: str = "",
) -> dict:
    """Build implement agent config — writes both code and tests in one session.

    Args:
        step: The plan step to implement.
        conventions: Pre-loaded convention text.
        plan_text: Full plan markdown text.
        prior_files: Paths to files created/modified in previous steps.
        extra_context: Optional additional context (failure output, etc.).
        explore_context: Codebase exploration context from the EXPLORE phase.
        prior_steps: Completed steps for plan truncation context.
        vault_context: Context from the vault (prior steps/runs).
        build_state: Current project file tree snapshot.

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("implement")

    reduced_plan = truncate_plan_for_step(plan_text, step, prior_steps or [])

    prior_files_block = "\n".join(f"- {f}" for f in prior_files) if prior_files else "- (none)"
    step_files_block = "\n".join(f"- {f}" for f in step.files) if step.files else "- (you decide file structure)"

    context = f"""

---

# Project Conventions

{conventions}

---

# Implementation Plan

{reduced_plan}

---

# Your Assignment: Step {step.number} — {step.title}

{step.description}

## Test classification: {step.test_classification}

## Files to create/modify

{step_files_block}

## Files from previous steps (already implemented)

{prior_files_block}"""

    if build_state:
        context += f"""

{build_state}"""

    if extra_context:
        context += f"""

## Additional Context

{extra_context}"""

    if explore_context:
        context += f"""

## Codebase Exploration Context

{explore_context}"""

    if vault_context:
        context += f"""

{vault_context}"""

    context += """

## Prior Work (vault)

Previous pipeline runs are stored in: agent_tools/dev_cycle/vault/
You may browse this directory to find prior attempts at similar work,
what was built, what failed, and what bugs were found.
Use Glob and Read as needed — this is optional but can save you from
repeating mistakes."""

    return {
        "prompt": base_prompt + context,
        "tools": list(_SDE_TOOLS),
        "model": _MODEL,
    }


def make_test_reviewer(
    conventions: str,
    diff: str,
    changed_files: list[str],
    step: PlanStep | None = None,
) -> dict:
    """Build test quality reviewer agent config.

    Args:
        conventions: Pre-loaded convention text.
        diff: Git diff for the step's changes.
        changed_files: List of file paths changed in this step.
        step: The plan step being reviewed (for intent context).

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("test_review")

    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "- (none)"

    context = f"""

---

# Project Conventions

{conventions}

---"""

    if step:
        context += f"""

# Step Intent: Step {step.number} — {step.title}

{step.description}

---"""

    context += f"""

# Changed Files

{files_block}

# Diff to Review

```diff
{diff}
```"""

    return {
        "prompt": base_prompt + context,
        "tools": list(_REVIEW_TOOLS),
        "model": _MODEL,
    }


def make_arch_reviewer(
    conventions: str,
    diff: str,
    changed_files: list[str],
    step: PlanStep | None = None,
) -> dict:
    """Build architecture reviewer agent config.

    Args:
        conventions: Pre-loaded convention text.
        diff: Git diff for the step's changes.
        changed_files: List of file paths changed in this step.
        step: The plan step being reviewed (for intent context).

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("arch_review")

    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "- (none)"

    context = f"""

---

# Project Conventions

{conventions}

---"""

    if step:
        context += f"""

# Step Intent: Step {step.number} — {step.title}

{step.description}

---"""

    context += f"""

# Changed Files

{files_block}

# Diff to Review

```diff
{diff}
```"""

    return {
        "prompt": base_prompt + context,
        "tools": list(_REVIEW_TOOLS),
        "model": _MODEL,
    }


def make_sde_agent(
    step: PlanStep,
    conventions: str,
    plan_text: str,
    test_files: list[str],
    prior_files: list[str],
    extra_context: str = "",
    explore_context: str = "",
    prior_steps: list[PlanStep] | None = None,
    vault_context: str = "",
) -> dict:
    """Build SDE agent config for a specific step.

    Args:
        step: The plan step to implement.
        conventions: Pre-loaded convention text.
        plan_text: Full plan markdown text.
        test_files: Paths to test files written for this step.
        prior_files: Paths to files created/modified in previous steps.
        extra_context: Optional additional context (failure output, etc.).
        explore_context: Codebase exploration context from the EXPLORE phase.
        prior_steps: Completed steps for plan truncation context.
        vault_context: Context from the vault (prior steps/runs).

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("sde")

    reduced_plan = truncate_plan_for_step(plan_text, step, prior_steps or [])

    test_files_block = "\n".join(f"- {f}" for f in test_files) if test_files else "- (none)"
    prior_files_block = "\n".join(f"- {f}" for f in prior_files) if prior_files else "- (none)"
    step_files_block = "\n".join(f"- {f}" for f in step.files) if step.files else "- (SDE decides file structure)"

    context = f"""

---

# Project Conventions

{conventions}

---

# Implementation Plan

{reduced_plan}

---

# Your Assignment: Step {step.number} — {step.title}

{step.description}

## Files to create/modify

{step_files_block}

## Test files (read these first — they are your spec)

{test_files_block}

## Files from previous steps (already implemented)

{prior_files_block}"""

    if extra_context:
        context += f"""

## Additional Context

{extra_context}"""

    if explore_context:
        context += f"""

## Codebase Exploration Context

{explore_context}"""

    if vault_context:
        context += f"""

{vault_context}"""

    context += """

## Prior Work (vault)

Previous pipeline runs are stored in: agent_tools/dev_cycle/vault/
You may browse this directory to find prior attempts at similar work,
what was built, what failed, and what bugs were found.
Use Glob and Read as needed — this is optional but can save you from
repeating mistakes."""

    return {
        "prompt": base_prompt + context,
        "tools": list(_SDE_TOOLS),
        "model": _MODEL,
    }


def make_test_eng_agent(
    step: PlanStep,
    conventions: str,
    plan_text: str,
    prior_files: list[str],
    explore_context: str = "",
    prior_steps: list[PlanStep] | None = None,
    vault_context: str = "",
) -> dict:
    """Build test-eng agent config for a specific step.

    Args:
        step: The plan step to write tests for.
        conventions: Pre-loaded convention text.
        plan_text: Full plan markdown text.
        prior_files: Paths to files created/modified in previous steps.
        explore_context: Codebase exploration context from the EXPLORE phase.
        prior_steps: Completed steps for plan truncation context.
        vault_context: Context from the vault (prior steps/runs).

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("test_eng")

    reduced_plan = truncate_plan_for_step(plan_text, step, prior_steps or [])

    prior_files_block = "\n".join(f"- {f}" for f in prior_files) if prior_files else "- (none)"
    step_files_block = "\n".join(f"- {f}" for f in step.files) if step.files else "- (SDE will decide file structure)"

    context = f"""

---

# Project Conventions

{conventions}

---

# Implementation Plan

{reduced_plan}

---

# Your Assignment: Write tests for Step {step.number} — {step.title}

{step.description}

## Test classification: {step.test_classification}

## Files this step will create/modify

{step_files_block}

## Files from previous steps (already implemented — you can import from these)

{prior_files_block}"""

    if explore_context:
        context += f"""

## Codebase Exploration Context

{explore_context}"""

    if vault_context:
        context += f"""

{vault_context}"""

    return {
        "prompt": base_prompt + context,
        "tools": list(_TEST_ENG_TOOLS),
        "model": _MODEL,
    }


def make_explore_agent(
    plan_text: str,
    plan_files: list[str],
    cwd: str,
) -> dict:
    """Build explore agent config for codebase research.

    Args:
        plan_text: Full plan markdown text.
        plan_files: Aggregated list of file paths from all plan steps.
        cwd: Repository root directory.

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("explore")

    files_block = "\n".join(f"- {f}" for f in plan_files) if plan_files else "- (none specified)"

    context = f"""

---

# Implementation Plan

{plan_text}

## Files this plan will create or modify

{files_block}

## Repository Root

`{cwd}`

Look in `plans/` for prior plans and `discussions/` for design decisions relevant to this work.
"""

    return {
        "prompt": base_prompt + context,
        "tools": list(_EXPLORE_TOOLS),
        "model": _MODEL,
    }


def make_review_agent(
    conventions: str,
    diff: str,
    changed_files: list[str],
    step: PlanStep | None = None,
) -> dict:
    """Build per-step convention review agent config.

    Args:
        conventions: Pre-loaded convention text.
        diff: Git diff for the step's changes.
        changed_files: List of file paths changed in this step.
        step: The plan step being reviewed (for intent context).

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("review")

    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "- (none)"

    context = f"""

---

# Project Conventions

{conventions}

---"""

    if step:
        context += f"""

# Step Intent: Step {step.number} — {step.title}

{step.description}

---"""

    context += f"""

# Changed Files

{files_block}

# Diff to Review

```diff
{diff}
```"""

    return {
        "prompt": base_prompt + context,
        "tools": list(_REVIEW_TOOLS),
        "model": _MODEL,
    }


def make_eng_review_agent(
    conventions: str,
    diff: str,
    changed_files: list[str],
    mechanical_scores: dict | None = None,
) -> dict:
    """Build eng-review agent config — fresh context, full diff.

    Args:
        conventions: Pre-loaded convention text.
        diff: Full branch diff.
        changed_files: List of all file paths changed in the branch.
        mechanical_scores: Optional dict of mechanical risk scores.
            These are the floor — the agent can upgrade but not downgrade.

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("eng_review")

    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "- (none)"

    context = f"""

---

# Project Conventions

{conventions}

---

# Changed Files

{files_block}

# Full Diff to Review

```diff
{diff}
```"""

    if mechanical_scores:
        scores_block = "\n".join(f"- **{k}**: {v}" for k, v in mechanical_scores.items())
        context += f"""

# Mechanical Risk Scores (floor — you can upgrade but not downgrade)

{scores_block}"""

    return {
        "prompt": base_prompt + context,
        "tools": list(_REVIEW_TOOLS),
        "model": _MODEL,
    }

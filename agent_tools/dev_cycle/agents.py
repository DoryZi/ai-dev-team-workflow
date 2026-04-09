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

_MODEL = "claude-sonnet-4-20250514"


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


def make_sde_agent(
    step: PlanStep,
    conventions: str,
    plan_text: str,
    test_files: list[str],
    prior_files: list[str],
    extra_context: str = "",
    explore_context: str = "",
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

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("sde")

    test_files_block = "\n".join(f"- {f}" for f in test_files) if test_files else "- (none)"
    prior_files_block = "\n".join(f"- {f}" for f in prior_files) if prior_files else "- (none)"
    step_files_block = "\n".join(f"- {f}" for f in step.files) if step.files else "- (SDE decides file structure)"

    context = f"""

---

# Project Conventions

{conventions}

---

# Implementation Plan

{plan_text}

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
) -> dict:
    """Build test-eng agent config for a specific step.

    Args:
        step: The plan step to write tests for.
        conventions: Pre-loaded convention text.
        plan_text: Full plan markdown text.
        prior_files: Paths to files created/modified in previous steps.
        explore_context: Codebase exploration context from the EXPLORE phase.

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("test_eng")

    prior_files_block = "\n".join(f"- {f}" for f in prior_files) if prior_files else "- (none)"
    step_files_block = "\n".join(f"- {f}" for f in step.files) if step.files else "- (SDE will decide file structure)"

    context = f"""

---

# Project Conventions

{conventions}

---

# Implementation Plan

{plan_text}

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
) -> dict:
    """Build per-step convention review agent config.

    Args:
        conventions: Pre-loaded convention text.
        diff: Git diff for the step's changes.
        changed_files: List of file paths changed in this step.

    Returns:
        Dict with keys ``prompt``, ``tools``, and ``model``.
    """
    base_prompt = _load_prompt("review")

    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "- (none)"

    context = f"""

---

# Project Conventions

{conventions}

---

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

"""Agent configuration builders for the dev-cycle pipeline.

Constructs prompt + tools + model dicts for the SDE and test-eng agents.
Each builder loads a base prompt from the prompts/ directory, then appends
step-specific context (plan, test files, prior files, conventions).
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
) -> dict:
    """Build SDE agent config for a specific step.

    Loads the SDE prompt, prepends project conventions, and appends
    step-specific context including the plan, test file paths, and
    prior implementation details.

    Args:
        step: The plan step to implement.
        conventions: Pre-loaded convention text.
        plan_text: Full plan markdown text.
        test_files: Paths to test files written for this step.
        prior_files: Paths to files created/modified in previous steps.
        extra_context: Optional additional context (failure output, etc.).

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
) -> dict:
    """Build test-eng agent config for a specific step.

    Loads the test-eng prompt, prepends project conventions, and appends
    step-specific context including the plan and prior implementation details.

    Args:
        step: The plan step to write tests for.
        conventions: Pre-loaded convention text.
        plan_text: Full plan markdown text.
        prior_files: Paths to files created/modified in previous steps.

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

    return {
        "prompt": base_prompt + context,
        "tools": list(_TEST_ENG_TOOLS),
        "model": _MODEL,
    }

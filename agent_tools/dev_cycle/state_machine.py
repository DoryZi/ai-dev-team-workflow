"""Explicit state machine for the TDD dev-cycle pipeline.

Defines the phases a step goes through and the transitions between them.
The pipeline orchestrator uses this to determine what to run next.
"""
from __future__ import annotations

from enum import Enum


class Phase(Enum):
    """Pipeline phases in execution order."""

    RED = "red"
    GREEN = "green"
    VERIFY = "verify"
    LINT = "lint"
    COMMIT = "commit"
    FINAL_REVIEW = "final_review"


# Per-step phase order (FINAL_REVIEW runs once after all steps)
_STEP_PHASES = [Phase.RED, Phase.GREEN, Phase.VERIFY, Phase.LINT, Phase.COMMIT]


def next_phase(current: Phase) -> Phase | None:
    """Return the next phase in the per-step cycle.

    Args:
        current: The phase that just completed.

    Returns:
        The next Phase, or None if the step cycle is complete.
    """
    try:
        idx = _STEP_PHASES.index(current)
    except ValueError:
        return None

    next_idx = idx + 1
    if next_idx < len(_STEP_PHASES):
        return _STEP_PHASES[next_idx]
    return None


def is_retryable(phase: Phase) -> bool:
    """Check if a phase supports retry loops.

    Args:
        phase: The phase to check.

    Returns:
        True if the phase can be retried on failure.
    """
    return phase in (Phase.VERIFY, Phase.LINT)


def phase_from_str(name: str) -> Phase:
    """Convert a string phase name to a Phase enum.

    Args:
        name: Phase name (e.g. "red", "green", "verify").

    Returns:
        The corresponding Phase enum value.

    Raises:
        ValueError: If the name doesn't match any phase.
    """
    name_clean = name.strip().lower().replace("-", "_")
    try:
        return Phase(name_clean)
    except ValueError:
        valid = ", ".join(p.value for p in Phase)
        raise ValueError(f"Unknown phase '{name}'. Valid phases: {valid}")

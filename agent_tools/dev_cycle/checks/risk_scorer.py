"""Deterministic risk scoring for code changes.

Applies simple rules based on file paths and diff content to score
risk across three categories: security, breaking_changes, rollback.

Used during the FINAL_REVIEW phase to provide context to /review.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_RISK_LEVELS = {"Low": 0, "Med": 1, "High": 2}

CATEGORIES = ["security", "breaking_changes", "rollback"]

# File-path-based rules: (pattern, category, minimum level)
_PATH_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(^|/)api/"), "breaking_changes", "Med"),
    (re.compile(r"(^|/)(config|infra|deploy)/"), "rollback", "Med"),
]

# Diff-content-based rules: (pattern, category, minimum level)
_DIFF_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bapi_key\b.*=.*[\"']"), "security", "High"),
    (re.compile(r"\bpassword\b.*=.*[\"']"), "security", "High"),
    (re.compile(r"\bsecret\b.*=.*[\"']"), "security", "High"),
    (re.compile(r"^-\s*def\s+[a-z_]", re.MULTILINE), "breaking_changes", "Med"),
]


def score_risk(diff: str, changed_files: list[str]) -> dict[str, str]:
    """Apply deterministic rules to score risk by category.

    Args:
        diff: Unified diff content (can be empty for path-only checks).
        changed_files: List of changed file paths relative to repo root.

    Returns:
        Dict mapping category to risk level ("Low", "Med", or "High").
    """
    scores: dict[str, str] = {cat: "Low" for cat in CATEGORIES}

    for file_path in changed_files:
        normalized = file_path.replace("\\", "/")

        for pattern, category, level in _PATH_RULES:
            if pattern.search(normalized):
                scores[category] = _max_level(scores[category], level)

        if _is_auth_path(normalized):
            scores["security"] = _max_level(scores["security"], "Med")

    if diff:
        for pattern, category, level in _DIFF_RULES:
            if pattern.search(diff):
                scores[category] = _max_level(scores[category], level)

    return scores


def merge_scores(
    mechanical: dict[str, str],
    llm: dict[str, str],
    policy: str = "max",
) -> dict[str, str]:
    """Merge mechanical and LLM risk scores.

    With "max" policy, LLM scores can upgrade but not downgrade
    the mechanical scores.

    Args:
        mechanical: Risk scores from deterministic rules.
        llm: Risk scores from LLM analysis.
        policy: Merge policy (only "max" supported).

    Returns:
        Merged risk scores.
    """
    if policy != "max":
        logger.warning("Unknown merge policy '%s', using 'max'", policy)

    merged: dict[str, str] = {}
    all_categories = set(mechanical.keys()) | set(llm.keys())

    for category in all_categories:
        mech_level = mechanical.get(category, "Low")
        llm_level = llm.get(category, "Low")
        merged[category] = _max_level(mech_level, llm_level)

    return merged


def _max_level(a: str, b: str) -> str:
    """Return the higher of two risk levels.

    Args:
        a: First risk level.
        b: Second risk level.

    Returns:
        The higher risk level.
    """
    return a if _RISK_LEVELS.get(a, 0) >= _RISK_LEVELS.get(b, 0) else b


def _is_auth_path(file_path: str) -> bool:
    """Check if a file path is in an auth/permissions area.

    Args:
        file_path: Normalized file path.

    Returns:
        True if the file relates to authentication or authorization.
    """
    indicators = ["/auth", "/permissions", "auth.py", "permissions.py"]
    lower_path = file_path.lower()
    return any(indicator in lower_path for indicator in indicators)

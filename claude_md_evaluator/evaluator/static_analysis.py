"""Static analysis scorer for generated code against CLAUDE.md rules.

Runs ruff and AST-based checks on Python source files, scoring adherence
to coding conventions extracted by the rule parser.
"""
from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING

from evaluator.checkers import (
    check_docstrings,
    check_error_handling,
    check_file_size,
    check_imports,
    check_paths,
    check_type_hints,
)
from evaluator.models import CheckResult, StaticAnalysisResult

if TYPE_CHECKING:
    from pathlib import Path

    from evaluator.rule_parser import Rule

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUFF_VIOLATION_DIVISOR = 20
_STATIC_CHECK_TYPES = frozenset({"static", "both"})

# ---------------------------------------------------------------------------
# Ruff integration
# ---------------------------------------------------------------------------


def _run_ruff(code_path: Path) -> tuple[list[str], float]:
    """Run ruff check on a file and return violations with a score.

    Args:
        code_path: Path to the Python file to check.

    Returns:
        Tuple of (violation_descriptions, score). Score is
        max(0, 1 - violation_count / 20).
    """
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format", "json", str(code_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ruff not found on PATH; skipping ruff check")
        return [], 1.0
    except subprocess.TimeoutExpired:
        logger.warning("ruff check timed out for %s", code_path)
        return ["ruff check timed out"], 0.0

    violations: list[str] = []
    try:
        diagnostics = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        logger.warning("Could not parse ruff JSON output")
        return [], 1.0

    for diag in diagnostics:
        code = diag.get("code", "???")
        message = diag.get("message", "")
        row = diag.get("location", {}).get("row", "?")
        violations.append(f"{code}: {message} (line {row})")

    score = max(0.0, 1.0 - len(violations) / RUFF_VIOLATION_DIVISOR)
    return violations, round(score, 4)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_CheckerFn = Callable[[str, "Rule"], CheckResult]

_CATEGORY_CHECKERS: dict[str, _CheckerFn] = {
    "type_hints": check_type_hints,
    "docstrings": check_docstrings,
    "imports": check_imports,
    "paths": check_paths,
    "error_handling": check_error_handling,
    "file_size": check_file_size,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_static_analysis(
    code_path: Path,
    rules: list[Rule],
) -> StaticAnalysisResult:
    """Run static analysis on generated code against parsed rules.

    Applies AST-based checks and ruff linting, returning per-rule scores
    and an aggregate result.  Rules with ``check_type == "llm"`` are skipped.

    Args:
        code_path: Path to a Python source file to analyse.
        rules: List of Rule objects from the rule parser.

    Returns:
        StaticAnalysisResult with individual check results and overall score.

    Raises:
        FileNotFoundError: If *code_path* does not exist.
    """
    if not code_path.exists():
        msg = f"Code file not found: {code_path}"
        raise FileNotFoundError(msg)

    source = code_path.read_text(encoding="utf-8")
    checks: list[CheckResult] = []

    for rule in rules:
        if rule.check_type not in _STATIC_CHECK_TYPES:
            logger.debug("Skipping LLM-only rule: %s", rule.id)
            continue

        checker = _CATEGORY_CHECKERS.get(rule.category)
        if checker is None:
            logger.debug("No static checker for category '%s' (rule %s)", rule.category, rule.id)
            continue

        check_result = checker(source, rule)
        checks.append(check_result)

    ruff_violations, ruff_score = _run_ruff(code_path)

    if checks or ruff_violations:
        checks.append(
            CheckResult(
                rule_id="ruff_check",
                rule_category="general",
                passed=ruff_score >= 1.0,
                score=ruff_score,
                details=f"{len(ruff_violations)} ruff violation(s) found.",
                violations=ruff_violations,
            )
        )

    overall = 0.0
    if checks:
        overall = round(sum(c.score for c in checks) / len(checks), 4)

    return StaticAnalysisResult(
        checks=checks,
        overall_score=overall,
        ruff_violations=ruff_violations,
    )

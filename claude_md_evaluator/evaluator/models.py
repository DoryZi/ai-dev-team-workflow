"""Data models for the static analysis pipeline.

Contains shared dataclasses used by both the checkers and the main
static analysis orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Result of a single rule check.

    Attributes:
        rule_id: Identifier of the rule that was checked.
        rule_category: Category of the rule (e.g. type_hints, imports).
        passed: Whether the check passed (score >= 1.0).
        score: Adherence score from 0.0 (total violation) to 1.0 (perfect).
        details: Human-readable explanation of the result.
        violations: Specific violations found during the check.
    """

    rule_id: str
    rule_category: str
    passed: bool
    score: float
    details: str
    violations: list[str] = field(default_factory=list)


@dataclass
class StaticAnalysisResult:
    """Aggregate static analysis results.

    Attributes:
        checks: Individual check results for each applicable rule.
        overall_score: Weighted average score across all checks (0.0-1.0).
        ruff_violations: Raw ruff output lines for reference.
    """

    checks: list[CheckResult] = field(default_factory=list)
    overall_score: float = 0.0
    ruff_violations: list[str] = field(default_factory=list)

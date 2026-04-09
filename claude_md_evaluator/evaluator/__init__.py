"""CLAUDE.md evaluation framework.

A comprehensive tool for evaluating CLAUDE.md files using coding problems,
static analysis, test execution, and LLM-as-judge scoring.
"""
from __future__ import annotations

__version__ = "0.1.0"
__author__ = "AI Dev Team Workflow"
__email__ = "noreply@example.com"

# Package-level exports
__all__ = [
    "CheckResult",
    "EvaluationReport",
    "Problem",
    "ProblemReport",
    "Rule",
    "StaticAnalysisResult",
    "TestResult",
    "TestRunResult",
    "__author__",
    "__email__",
    "__version__",
    "build_evaluation_report",
    "build_problem_report",
    "discover_problems",
    "get_builtin_problems",
    "load_problem",
    "load_report",
    "parse_claude_md",
    "parse_claude_md_text",
    "render_html_from_json",
    "render_html_report",
    "run_static_analysis",
    "run_tests",
    "save_report",
]

from evaluator.problems import Problem, discover_problems, get_builtin_problems, load_problem
from evaluator.report import (
    EvaluationReport,
    ProblemReport,
    build_evaluation_report,
    build_problem_report,
    load_report,
    save_report,
)
from evaluator.html_renderer import render_html_from_json, render_html_report
from evaluator.rule_parser import Rule, parse_claude_md, parse_claude_md_text
from evaluator.static_analysis import CheckResult, StaticAnalysisResult, run_static_analysis
from evaluator.test_runner import TestResult, TestRunResult, run_tests

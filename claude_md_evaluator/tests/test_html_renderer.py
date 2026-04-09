"""Tests for the HTML report renderer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluator.html_renderer import render_html_from_json, render_html_report


@pytest.fixture()
def sample_report() -> dict:
    """Full sample evaluation report for testing."""
    return {
        "claude_md_file": "test_project/CLAUDE.md",
        "timestamp": "2026-04-01T12:00:00Z",
        "aggregate_score": 0.82,
        "aggregate_scores": {
            "generation": 1.0,
            "static_analysis": 0.75,
            "tests": 0.9,
            "llm_judge": 0.65,
        },
        "problems": [
            {
                "name": "fibonacci",
                "combined_score": 0.85,
                "generation": {
                    "success": True,
                    "duration_seconds": 3.2,
                },
                "static_analysis": {
                    "overall_score": 0.8,
                    "checks": [
                        {
                            "rule_id": "type_hints_required",
                            "score": 1.0,
                            "details": "All functions have type hints",
                        },
                        {
                            "rule_id": "docstrings_required",
                            "score": 0.5,
                            "details": "Missing docstring on helper function",
                        },
                    ],
                },
                "test_results": {
                    "total_tests": 5,
                    "passed_tests": 4,
                    "test_results": [
                        {"name": "test_fib_zero", "passed": True, "error_message": None},
                        {"name": "test_fib_one", "passed": True, "error_message": None},
                        {"name": "test_fib_ten", "passed": True, "error_message": None},
                        {"name": "test_fib_negative", "passed": True, "error_message": None},
                        {
                            "name": "test_fib_large",
                            "passed": False,
                            "error_message": "AssertionError: expected 55, got 54",
                        },
                    ],
                },
                "llm_judge": {
                    "overall_score": 0.7,
                    "summary": "Good implementation with minor issues.",
                    "dimensions": [
                        {
                            "name": "correctness",
                            "score": 0.9,
                            "reasoning": "Handles most cases well.",
                        },
                        {
                            "name": "readability",
                            "score": 0.5,
                            "reasoning": "Variable names could be more descriptive.",
                        },
                    ],
                },
            },
        ],
        "metadata": {
            "version": "0.1.0",
            "model": "claude-sonnet-4-20250514",
            "total_duration_seconds": 45.7,
        },
    }


@pytest.fixture()
def minimal_report() -> dict:
    """Minimal report with almost no data."""
    return {}


class TestRenderHtmlReport:
    """Tests for render_html_report."""

    def test_produces_valid_html(self, sample_report: dict, tmp_path: Path) -> None:
        """Rendered output is valid HTML with expected structure."""
        out = tmp_path / "report.html"
        result = render_html_report(sample_report, out)

        assert result == out
        html = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_output_file_created(self, sample_report: dict, tmp_path: Path) -> None:
        """Output file is actually written to disk."""
        out = tmp_path / "subdir" / "report.html"
        render_html_report(sample_report, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_contains_problem_name(self, sample_report: dict, tmp_path: Path) -> None:
        """Report includes the problem name from the data."""
        out = tmp_path / "report.html"
        render_html_report(sample_report, out)
        html = out.read_text(encoding="utf-8")
        assert "fibonacci" in html

    def test_contains_aggregate_score(self, sample_report: dict, tmp_path: Path) -> None:
        """Report includes the aggregate score."""
        out = tmp_path / "report.html"
        render_html_report(sample_report, out)
        html = out.read_text(encoding="utf-8")
        assert "82%" in html

    def test_contains_score_color_classes(self, sample_report: dict, tmp_path: Path) -> None:
        """Report uses color classes based on score thresholds."""
        out = tmp_path / "report.html"
        render_html_report(sample_report, out)
        html = out.read_text(encoding="utf-8")
        # 0.82 aggregate => bg-green
        assert "bg-green" in html

    def test_minimal_report_renders(self, minimal_report: dict, tmp_path: Path) -> None:
        """An empty/minimal report dict renders without errors."""
        out = tmp_path / "report.html"
        result = render_html_report(minimal_report, out)
        assert result == out
        html = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "No problem results available" in html

    def test_missing_llm_judge_renders(self, tmp_path: Path) -> None:
        """A problem with no LLM judge section renders gracefully."""
        report = {
            "problems": [
                {
                    "name": "no_llm",
                    "combined_score": 0.5,
                    "generation": {"success": True, "duration_seconds": 1.0},
                }
            ],
        }
        out = tmp_path / "report.html"
        render_html_report(report, out)
        html = out.read_text(encoding="utf-8")
        assert "no_llm" in html
        # The problem body should not contain the LLM Judge subsection heading
        # (the score grid always shows the label, so check within the problem body)
        problem_body_start = html.index("no_llm")
        problem_body_html = html[problem_body_start:]
        # No LLM dimension cards should be rendered
        assert "dim-card" not in problem_body_html

    def test_self_contained_no_external_refs(
        self, sample_report: dict, tmp_path: Path
    ) -> None:
        """HTML has no external stylesheet or script references."""
        out = tmp_path / "report.html"
        render_html_report(sample_report, out)
        html = out.read_text(encoding="utf-8")
        assert 'rel="stylesheet"' not in html
        assert '<script src=' not in html


class TestRenderHtmlFromJson:
    """Tests for render_html_from_json."""

    def test_loads_and_renders(self, sample_report: dict, tmp_path: Path) -> None:
        """JSON file is loaded and rendered to HTML."""
        json_file = tmp_path / "report.json"
        json_file.write_text(json.dumps(sample_report), encoding="utf-8")

        result = render_html_from_json(json_file)
        assert result == tmp_path / "report.html"
        assert result.exists()

    def test_custom_output_path(self, sample_report: dict, tmp_path: Path) -> None:
        """Custom output path is respected."""
        json_file = tmp_path / "input.json"
        json_file.write_text(json.dumps(sample_report), encoding="utf-8")
        custom = tmp_path / "custom" / "out.html"

        result = render_html_from_json(json_file, output_path=custom)
        assert result == custom
        assert custom.exists()

    def test_missing_json_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError when JSON path does not exist."""
        with pytest.raises(FileNotFoundError):
            render_html_from_json(tmp_path / "nonexistent.json")

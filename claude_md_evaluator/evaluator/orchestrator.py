"""Orchestrator that wires together all evaluation pipeline stages.

Coordinates code generation, static analysis, test execution, and
LLM-as-judge scoring for one or more CLAUDE.md files against a set
of coding problems.  Produces JSON and (optionally) HTML reports.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

from evaluator.llm_judge import (
    LLMJudgeResult,
    RubricDimension,
    evaluate_with_llm,
    get_default_rubric,
    load_rubric,
)
from evaluator.problems import Problem, get_builtin_problems
from evaluator.rule_parser import Rule, parse_claude_md
from evaluator.runner import GenerationResult, generate_solution
from evaluator.static_analysis import StaticAnalysisResult, run_static_analysis
from evaluator.test_runner import TestRunResult, run_tests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-problem evaluation
# ---------------------------------------------------------------------------


async def evaluate_single_problem(
    claude_md_path: Path,
    problem: Problem,
    rules: list[Rule],
    rubric: list[RubricDimension],
    timeout: int = 120,
) -> dict:
    """Run the full evaluation pipeline for one problem.

    Sequentially: generate solution, run static analysis, run tests,
    and invoke the LLM judge.  Returns a dictionary with all collected
    results plus timing information.

    Args:
        claude_md_path: Path to the CLAUDE.md file being evaluated.
        problem: The coding problem to solve.
        rules: Parsed rules from the CLAUDE.md file.
        rubric: Rubric dimensions for LLM judging.
        timeout: Maximum seconds for code generation.

    Returns:
        Dictionary containing generation, static_analysis, tests, and
        llm_judge result sub-dicts, plus overall timing.
    """
    result: dict = {"problem": problem.name, "phases": {}}
    overall_start = time.monotonic()
    temp_dir: Path | None = None

    try:
        # --- Phase 1: Code generation ---
        phase_start = time.monotonic()
        _log_phase(problem.name, "generation")
        gen_result: GenerationResult = generate_solution(
            claude_md_path, problem, timeout=timeout
        )
        temp_dir = gen_result.temp_dir
        result["phases"]["generation"] = {
            "success": gen_result.success,
            "duration_seconds": round(time.monotonic() - phase_start, 2),
            "solution_chars": len(gen_result.solution_code),
        }

        if not gen_result.success:
            logger.warning("Generation failed for '%s'; skipping remaining phases", problem.name)
            result["phases"]["static_analysis"] = _skipped_phase("generation failed")
            result["phases"]["tests"] = _skipped_phase("generation failed")
            result["phases"]["llm_judge"] = _skipped_phase("generation failed")
            return result

        # --- Phase 2: Static analysis ---
        phase_start = time.monotonic()
        _log_phase(problem.name, "static analysis")
        sa_result: StaticAnalysisResult = run_static_analysis(gen_result.solution_path, rules)
        result["phases"]["static_analysis"] = {
            "overall_score": sa_result.overall_score,
            "checks_count": len(sa_result.checks),
            "ruff_violations": len(sa_result.ruff_violations),
            "duration_seconds": round(time.monotonic() - phase_start, 2),
            "checks": [asdict(c) for c in sa_result.checks],
        }

        # --- Phase 3: Test execution ---
        phase_start = time.monotonic()
        _log_phase(problem.name, "tests")
        test_result: TestRunResult = run_tests(
            gen_result.temp_dir, problem.test_dir, timeout=30
        )
        result["phases"]["tests"] = {
            "passed": test_result.passed,
            "total_tests": test_result.total_tests,
            "passed_tests": test_result.passed_tests,
            "failed_tests": test_result.failed_tests,
            "duration_seconds": round(time.monotonic() - phase_start, 2),
        }

        # --- Phase 4: LLM judge ---
        phase_start = time.monotonic()
        _log_phase(problem.name, "LLM judge")
        reference_code: str | None = None
        if problem.reference_solution_path.is_file():
            reference_code = problem.reference_solution_path.read_text(encoding="utf-8")

        llm_result: LLMJudgeResult = await evaluate_with_llm(
            code=gen_result.solution_code,
            problem_prompt=problem.prompt,
            rules=rules,
            rubric=rubric,
            reference_solution=reference_code,
        )
        result["phases"]["llm_judge"] = {
            "overall_score": llm_result.overall_score,
            "summary": llm_result.summary,
            "dimensions": [asdict(d) for d in llm_result.dimensions],
            "rule_adherence_notes": llm_result.rule_adherence_notes,
            "duration_seconds": round(time.monotonic() - phase_start, 2),
        }

    except Exception:
        logger.exception("Error evaluating problem '%s'", problem.name)
        result["error"] = f"Unexpected error during evaluation of {problem.name}"
    finally:
        # Clean up temp directory
        if temp_dir is not None and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                logger.debug("Cleaned up temp dir: %s", temp_dir)
            except OSError:
                logger.warning("Failed to clean up temp dir: %s", temp_dir)

    result["duration_seconds"] = round(time.monotonic() - overall_start, 2)
    return result


# ---------------------------------------------------------------------------
# Single CLAUDE.md evaluation
# ---------------------------------------------------------------------------


async def evaluate_claude_md(
    claude_md_path: Path,
    problems: list[Problem],
    output_dir: Path,
    rubric_path: Path | None = None,
    timeout: int = 120,
) -> Path:
    """Evaluate a single CLAUDE.md file against all problems.

    Parses rules, loads the rubric, evaluates each problem, builds a
    JSON report, and optionally renders an HTML report.

    Args:
        claude_md_path: Path to the CLAUDE.md to evaluate.
        problems: List of coding problems to evaluate against.
        output_dir: Directory to write report files into.
        rubric_path: Optional custom rubric YAML.  Uses default if None.
        timeout: Maximum seconds for each code generation call.

    Returns:
        Path to the generated report (HTML if renderer available, else JSON).
    """
    _print_progress(f"Evaluating {claude_md_path.name} against {len(problems)} problems...")

    # 1. Parse rules
    rules = parse_claude_md(claude_md_path)
    logger.info("Parsed %d rules from %s", len(rules), claude_md_path)

    # 2. Load rubric
    rubric = _load_rubric(rubric_path)

    # 3. Evaluate each problem
    problem_results: list[dict] = []
    for problem in problems:
        _print_progress(f"  Problem: {problem.name}")
        problem_result = await evaluate_single_problem(
            claude_md_path, problem, rules, rubric, timeout=timeout
        )
        problem_results.append(problem_result)

    # 4. Build report data
    report_data = _build_report_data(claude_md_path, problem_results, rules)

    # 5. Save JSON report
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = claude_md_path.stem
    json_path = output_dir / f"{stem}_report.json"
    json_path.write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")
    logger.info("JSON report saved to %s", json_path)

    # 6. Try to render HTML report (graceful fallback if modules not available)
    html_path = _try_render_html(report_data, output_dir, stem)
    if html_path is not None:
        _print_progress(f"Report saved to {html_path}")
        return html_path

    _print_progress(f"Report saved to {json_path}")
    return json_path


# ---------------------------------------------------------------------------
# Multi-file evaluation
# ---------------------------------------------------------------------------


async def run_evaluation(
    claude_md_files: list[Path],
    problems: list[Problem],
    output_dir: Path,
    rubric_path: Path | None = None,
    timeout: int = 120,
) -> list[Path]:
    """Evaluate multiple CLAUDE.md files.

    Loops through each file, calling :func:`evaluate_claude_md` for each.

    Args:
        claude_md_files: Paths to CLAUDE.md files to evaluate.
        problems: Coding problems to evaluate against.
        output_dir: Directory for report output.
        rubric_path: Optional custom rubric YAML path.
        timeout: Maximum seconds per code generation call.

    Returns:
        List of report paths (one per CLAUDE.md file).
    """
    report_paths: list[Path] = []

    for file_path in claude_md_files:
        try:
            report_path = await evaluate_claude_md(
                file_path, problems, output_dir,
                rubric_path=rubric_path, timeout=timeout,
            )
            report_paths.append(report_path)
        except Exception:
            logger.exception("Failed to evaluate %s", file_path)
            _print_progress(f"ERROR: Failed to evaluate {file_path}")

    return report_paths


# ---------------------------------------------------------------------------
# Problem filtering
# ---------------------------------------------------------------------------


def resolve_problems(problem_names: list[str]) -> list[Problem]:
    """Resolve problem name list to Problem objects.

    If the list is ``["all"]``, returns all built-in problems.
    Otherwise filters built-in problems by name.

    Args:
        problem_names: List of problem names, or ``["all"]``.

    Returns:
        Matching Problem objects.

    Raises:
        SystemExit: If a requested problem name is not found.
    """
    builtin = get_builtin_problems()

    if problem_names == ["all"]:
        return builtin

    available = {p.name: p for p in builtin}
    selected: list[Problem] = []

    for name in problem_names:
        if name not in available:
            logger.error(
                "Problem '%s' not found.  Available: %s",
                name,
                ", ".join(sorted(available)),
            )
            sys.exit(1)
        selected.append(available[name])

    return selected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log_phase(problem_name: str, phase_name: str) -> None:
    """Log the start of a pipeline phase."""
    logger.info("[%s] Starting %s", problem_name, phase_name)


def _print_progress(message: str) -> None:
    """Print progress to stderr so stdout stays clean for piping."""
    print(message, file=sys.stderr)


def _skipped_phase(reason: str) -> dict:
    """Return a placeholder dict for a phase that was skipped.

    Args:
        reason: Why the phase was skipped.

    Returns:
        Dictionary with skipped=True and the reason.
    """
    return {"skipped": True, "reason": reason}


def _load_rubric(rubric_path: Path | None) -> list[RubricDimension]:
    """Load rubric from a path or fall back to the built-in default.

    Args:
        rubric_path: Optional path to a custom rubric YAML file.

    Returns:
        List of RubricDimension objects.
    """
    if rubric_path is not None:
        logger.info("Loading custom rubric from %s", rubric_path)
        return load_rubric(rubric_path)
    return get_default_rubric()


def _build_report_data(
    claude_md_path: Path,
    problem_results: list[dict],
    rules: list[Rule],
) -> dict:
    """Assemble the full evaluation report dictionary.

    Tries to use ``report.py``'s ``build_evaluation_report`` if available;
    falls back to a simple dictionary structure.

    Args:
        claude_md_path: Path to the evaluated CLAUDE.md.
        problem_results: Per-problem result dicts.
        rules: Parsed rules from the CLAUDE.md.

    Returns:
        Report dictionary ready for JSON serialization.
    """
    try:
        from evaluator.report import build_evaluation_report
        return build_evaluation_report(claude_md_path, problem_results, rules)
    except ImportError:
        logger.debug("report.py not available; using fallback report structure")

    return {
        "claude_md": str(claude_md_path),
        "rules_count": len(rules),
        "problems": problem_results,
        "summary": _compute_summary(problem_results),
    }


def _compute_summary(problem_results: list[dict]) -> dict:
    """Compute a simple summary from problem results.

    Args:
        problem_results: List of per-problem result dicts.

    Returns:
        Summary dict with counts and average scores.
    """
    total = len(problem_results)
    if total == 0:
        return {"total_problems": 0}

    sa_scores: list[float] = []
    test_passes = 0
    llm_scores: list[float] = []

    for pr in problem_results:
        phases = pr.get("phases", {})

        sa = phases.get("static_analysis", {})
        if not sa.get("skipped") and "overall_score" in sa:
            sa_scores.append(sa["overall_score"])

        tests = phases.get("tests", {})
        if not tests.get("skipped") and tests.get("passed"):
            test_passes += 1

        llm = phases.get("llm_judge", {})
        if not llm.get("skipped") and "overall_score" in llm:
            llm_scores.append(llm["overall_score"])

    return {
        "total_problems": total,
        "avg_static_analysis_score": round(sum(sa_scores) / len(sa_scores), 4) if sa_scores else 0.0,
        "test_pass_rate": round(test_passes / total, 4),
        "avg_llm_judge_score": round(sum(llm_scores) / len(llm_scores), 4) if llm_scores else 0.0,
    }


def _try_render_html(report_data: dict, output_dir: Path, stem: str) -> Path | None:
    """Attempt to render an HTML report using html_renderer.

    Args:
        report_data: The full report dictionary.
        output_dir: Directory to write the HTML file into.
        stem: Filename stem for the output file.

    Returns:
        Path to the HTML file if rendering succeeded, None otherwise.
    """
    try:
        from evaluator.html_renderer import render_html_report
        html_path = output_dir / f"{stem}_report.html"
        html_content = render_html_report(report_data)
        html_path.write_text(html_content, encoding="utf-8")
        logger.info("HTML report saved to %s", html_path)
        return html_path
    except ImportError:
        logger.debug("html_renderer.py not available; skipping HTML rendering")
        return None
    except Exception:
        logger.warning("HTML rendering failed; JSON report is still available")
        return None

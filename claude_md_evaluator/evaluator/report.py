"""Report aggregator for evaluation results.

Collects results from all evaluation phases (generation, static analysis,
test execution, LLM judge) and produces structured JSON reports that can
be saved, loaded, and compared across evaluations.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from evaluator.llm_judge import DimensionScore, LLMJudgeResult
from evaluator.models import CheckResult, StaticAnalysisResult
from evaluator.runner import GenerationResult
from evaluator.test_runner import TestResult, TestRunResult

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"

# Score weights for the combined score
_WEIGHT_TESTS = 0.40
_WEIGHT_STATIC = 0.25
_WEIGHT_LLM = 0.25
_WEIGHT_GENERATION = 0.10


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ProblemReport:
    """Results for a single problem.

    Attributes:
        problem_name: Name of the evaluated problem.
        generation: Generation phase summary (duration, success).
        static_analysis: Static analysis summary (overall_score, per-check).
        test_results: Test execution summary (passed, total, failed, details).
        llm_judge: LLM judge summary (overall_score, per-dimension).
        combined_score: Weighted combination of all phase scores.
    """

    problem_name: str
    generation: dict = field(default_factory=dict)
    static_analysis: dict = field(default_factory=dict)
    test_results: dict = field(default_factory=dict)
    llm_judge: dict = field(default_factory=dict)
    combined_score: float = 0.0


@dataclass
class EvaluationReport:
    """Full evaluation report for one CLAUDE.md file.

    Attributes:
        claude_md_path: Absolute path to the evaluated CLAUDE.md.
        claude_md_name: Basename for display purposes.
        timestamp: ISO-8601 formatted timestamp of report creation.
        problems: Per-problem reports.
        aggregate_score: Mean of all problem combined_scores.
        total_duration_seconds: Wall-clock duration for the full evaluation.
        metadata: Additional info (version, model, problem count).
    """

    claude_md_path: str
    claude_md_name: str
    timestamp: str
    problems: list[ProblemReport] = field(default_factory=list)
    aggregate_score: float = 0.0
    total_duration_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _compute_test_pass_rate(test_run: TestRunResult) -> float:
    """Compute pass rate from test results.

    Args:
        test_run: Aggregate test run result.

    Returns:
        Float between 0.0 and 1.0, or 0.0 when no tests exist.
    """
    if test_run.total_tests == 0:
        return 0.0
    return test_run.passed_tests / test_run.total_tests


def _compute_combined_score(
    generation_success: bool,
    static_score: float,
    test_pass_rate: float,
    llm_score: float,
) -> float:
    """Compute weighted combined score from all phase scores.

    Args:
        generation_success: Whether code generation succeeded.
        static_score: Static analysis overall score (0.0-1.0).
        test_pass_rate: Fraction of tests that passed (0.0-1.0).
        llm_score: LLM judge overall score (0.0-1.0).

    Returns:
        Weighted combination clamped to [0.0, 1.0].
    """
    gen_score = 1.0 if generation_success else 0.0
    raw = (
        _WEIGHT_TESTS * test_pass_rate
        + _WEIGHT_STATIC * static_score
        + _WEIGHT_LLM * llm_score
        + _WEIGHT_GENERATION * gen_score
    )
    return max(0.0, min(1.0, raw))


def _serialize_generation(gen: GenerationResult) -> dict:
    """Serialize generation result to a plain dict.

    Args:
        gen: The generation result to serialize.

    Returns:
        Dict with duration and success fields.
    """
    return {
        "duration_seconds": gen.duration_seconds,
        "success": gen.success,
    }


def _serialize_static_analysis(sa: StaticAnalysisResult) -> dict:
    """Serialize static analysis result to a plain dict.

    Args:
        sa: The static analysis result to serialize.

    Returns:
        Dict with overall_score, checks summary, and ruff violations.
    """
    checks = []
    for check in sa.checks:
        checks.append({
            "rule_id": check.rule_id,
            "rule_category": check.rule_category,
            "passed": check.passed,
            "score": check.score,
            "details": check.details,
            "violations": check.violations,
        })
    return {
        "overall_score": sa.overall_score,
        "checks": checks,
        "ruff_violations": sa.ruff_violations,
    }


def _serialize_test_results(tr: TestRunResult) -> dict:
    """Serialize test run result to a plain dict.

    Args:
        tr: The test run result to serialize.

    Returns:
        Dict with pass/fail counts and per-test details.
    """
    details = []
    for t in tr.test_results:
        entry: dict = {
            "name": t.name,
            "passed": t.passed,
            "duration_seconds": t.duration_seconds,
        }
        if t.error_message is not None:
            entry["error_message"] = t.error_message
        details.append(entry)
    return {
        "passed": tr.passed,
        "total": tr.total_tests,
        "passed_count": tr.passed_tests,
        "failed_count": tr.failed_tests,
        "duration_seconds": tr.duration_seconds,
        "details": details,
    }


def _serialize_llm_judge(lj: LLMJudgeResult) -> dict:
    """Serialize LLM judge result to a plain dict.

    Args:
        lj: The LLM judge result to serialize.

    Returns:
        Dict with overall_score, per-dimension scores, summary, and notes.
    """
    dimensions = []
    for dim in lj.dimensions:
        dimensions.append({
            "name": dim.name,
            "score": dim.score,
            "weight": dim.weight,
            "reasoning": dim.reasoning,
        })
    return {
        "overall_score": lj.overall_score,
        "dimensions": dimensions,
        "summary": lj.summary,
        "rule_adherence_notes": lj.rule_adherence_notes,
    }


def build_problem_report(
    problem_name: str,
    generation: GenerationResult,
    static_analysis: StaticAnalysisResult,
    test_results: TestRunResult,
    llm_judge: LLMJudgeResult,
) -> ProblemReport:
    """Build a report for a single problem from evaluation results.

    Args:
        problem_name: Identifier for the problem.
        generation: Code generation result.
        static_analysis: Static analysis result.
        test_results: Test execution result.
        llm_judge: LLM judge result.

    Returns:
        A fully populated ProblemReport with computed combined_score.
    """
    test_pass_rate = _compute_test_pass_rate(test_results)
    combined = _compute_combined_score(
        generation_success=generation.success,
        static_score=static_analysis.overall_score,
        test_pass_rate=test_pass_rate,
        llm_score=llm_judge.overall_score,
    )

    return ProblemReport(
        problem_name=problem_name,
        generation=_serialize_generation(generation),
        static_analysis=_serialize_static_analysis(static_analysis),
        test_results=_serialize_test_results(test_results),
        llm_judge=_serialize_llm_judge(llm_judge),
        combined_score=combined,
    )


def build_evaluation_report(
    claude_md_path: Path,
    problem_reports: list[ProblemReport],
    total_duration: float,
    metadata: dict | None = None,
) -> EvaluationReport:
    """Build the full evaluation report.

    Args:
        claude_md_path: Path to the evaluated CLAUDE.md file.
        problem_reports: List of per-problem reports.
        total_duration: Total wall-clock seconds for the evaluation.
        metadata: Optional extra metadata to include.

    Returns:
        A complete EvaluationReport with aggregate score.
    """
    if problem_reports:
        aggregate = sum(p.combined_score for p in problem_reports) / len(problem_reports)
    else:
        aggregate = 0.0

    base_metadata: dict = {
        "evaluator_version": _VERSION,
        "num_problems": len(problem_reports),
    }
    if metadata:
        base_metadata.update(metadata)

    return EvaluationReport(
        claude_md_path=str(claude_md_path),
        claude_md_name=claude_md_path.name,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        problems=problem_reports,
        aggregate_score=aggregate,
        total_duration_seconds=total_duration,
        metadata=base_metadata,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _report_to_dict(report: EvaluationReport) -> dict:
    """Convert an EvaluationReport to a JSON-serializable dict.

    Uses dataclasses.asdict for clean recursive conversion.

    Args:
        report: The report to convert.

    Returns:
        Plain dict suitable for json.dumps.
    """
    return asdict(report)


def _report_from_dict(data: dict) -> EvaluationReport:
    """Reconstruct an EvaluationReport from a plain dict.

    Args:
        data: Dict as produced by _report_to_dict / loaded from JSON.

    Returns:
        Reconstructed EvaluationReport.
    """
    problems = [ProblemReport(**p) for p in data.get("problems", [])]
    return EvaluationReport(
        claude_md_path=data["claude_md_path"],
        claude_md_name=data["claude_md_name"],
        timestamp=data["timestamp"],
        problems=problems,
        aggregate_score=data["aggregate_score"],
        total_duration_seconds=data["total_duration_seconds"],
        metadata=data.get("metadata", {}),
    )


def save_report(report: EvaluationReport, output_dir: Path) -> Path:
    """Save report as pretty-printed JSON.

    Filename format: ``{claude_md_name}_{timestamp}.json`` where the
    timestamp uses dashes/underscores for filesystem compatibility.

    Args:
        report: The evaluation report to persist.
        output_dir: Directory to write the JSON file into.

    Returns:
        Path to the written JSON file.

    Raises:
        OSError: If the directory cannot be created or file cannot be written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build a filesystem-safe timestamp
    safe_ts = report.timestamp.replace(":", "-").replace("+", "_plus_")
    stem = report.claude_md_name.replace(".", "_")
    filename = f"{stem}_{safe_ts}.json"
    file_path = output_dir / filename

    data = _report_to_dict(report)
    file_path.write_text(
        json.dumps(data, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Saved evaluation report to %s", file_path)
    return file_path


def load_report(path: Path) -> EvaluationReport:
    """Load a report from a JSON file.

    Args:
        path: Path to the JSON report file.

    Returns:
        Reconstructed EvaluationReport.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return _report_from_dict(data)

"""LLM-as-judge evaluator for code quality assessment.

Uses Claude via the Anthropic API to score code on configurable rubric
dimensions.  Each dimension receives a 0.0-1.0 score with reasoning,
and an overall weighted score is computed.  CLAUDE.md rules are included
in the evaluation prompt so the judge can note rule adherence.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from evaluator.rule_parser import Rule

logger = logging.getLogger(__name__)

_RUBRICS_DIR = Path(__file__).resolve().parent.parent / "rubrics"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RubricDimension:
    """A rubric dimension loaded from YAML.

    Attributes:
        name: Human-readable dimension name (e.g. "readability").
        weight: Relative weight for the weighted average (0.0-1.0).
        description: What this dimension measures.
        criteria: Specific criteria the judge should evaluate.
    """

    name: str
    weight: float
    description: str
    criteria: list[str]


@dataclass(frozen=True)
class DimensionScore:
    """Score for a single rubric dimension.

    Attributes:
        name: Dimension name matching the rubric.
        score: Numeric score from 0.0 (worst) to 1.0 (best).
        weight: Weight used in the overall calculation.
        reasoning: The LLM judge's explanation for the score.
    """

    name: str
    score: float
    weight: float
    reasoning: str


@dataclass(frozen=True)
class LLMJudgeResult:
    """Result of LLM-as-judge evaluation.

    Attributes:
        dimensions: Per-dimension scores with reasoning.
        overall_score: Weighted average of dimension scores.
        summary: Overall assessment narrative.
        rule_adherence_notes: Notes on CLAUDE.md rule compliance.
    """

    dimensions: list[DimensionScore]
    overall_score: float
    summary: str
    rule_adherence_notes: list[str]


# ---------------------------------------------------------------------------
# Rubric loading
# ---------------------------------------------------------------------------


def load_rubric(rubric_path: Path) -> list[RubricDimension]:
    """Load rubric dimensions from a YAML file.

    Args:
        rubric_path: Path to a YAML file with a top-level ``dimensions`` key.

    Returns:
        List of RubricDimension objects.

    Raises:
        FileNotFoundError: If *rubric_path* does not exist.
        ValueError: If the YAML structure is invalid or weights are out of range.
    """
    raw = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "dimensions" not in raw:
        msg = f"Rubric YAML must contain a top-level 'dimensions' key: {rubric_path}"
        raise ValueError(msg)

    dimensions_raw = raw["dimensions"]
    if not isinstance(dimensions_raw, dict) or not dimensions_raw:
        msg = f"Rubric 'dimensions' must be a non-empty mapping: {rubric_path}"
        raise ValueError(msg)

    dimensions: list[RubricDimension] = []
    for name, spec in dimensions_raw.items():
        weight = float(spec.get("weight", 0.0))
        if not 0.0 <= weight <= 1.0:
            msg = f"Weight for dimension '{name}' must be between 0.0 and 1.0, got {weight}"
            raise ValueError(msg)

        description = str(spec.get("description", ""))
        criteria = list(spec.get("criteria", []))
        dimensions.append(
            RubricDimension(
                name=str(name),
                weight=weight,
                description=description,
                criteria=criteria,
            )
        )

    return dimensions


def get_default_rubric() -> list[RubricDimension]:
    """Load the built-in default rubric shipped with the package.

    Returns:
        List of RubricDimension objects from ``rubrics/default.yaml``.

    Raises:
        FileNotFoundError: If the default rubric file is missing.
    """
    default_path = _RUBRICS_DIR / "default.yaml"
    return load_rubric(default_path)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_evaluation_prompt(
    code: str,
    problem_prompt: str,
    rules: list[Rule],
    rubric: list[RubricDimension],
    reference_solution: str | None = None,
) -> str:
    """Build the system+user prompt for the LLM judge.

    Args:
        code: The code to evaluate.
        problem_prompt: Description of the problem the code solves.
        rules: CLAUDE.md rules the code should adhere to.
        rubric: Rubric dimensions with criteria.
        reference_solution: Optional reference implementation for comparison.

    Returns:
        The fully assembled prompt string.
    """
    rubric_section = _format_rubric(rubric)
    rules_section = _format_rules(rules)

    parts: list[str] = [
        "You are an expert code reviewer acting as an LLM judge.",
        "Evaluate the following code against the rubric dimensions below.",
        "For each dimension, provide a score from 0.0 to 1.0 and a brief reasoning.",
        "Also note any adherence or violations of the coding rules provided.",
        "",
        "## Problem",
        problem_prompt,
        "",
        "## Code to Evaluate",
        "```python",
        code,
        "```",
    ]

    if reference_solution:
        parts.extend(
            [
                "",
                "## Reference Solution",
                "```python",
                reference_solution,
                "```",
            ]
        )

    parts.extend(["", "## Rubric", rubric_section])

    if rules:
        parts.extend(["", "## Coding Rules (from CLAUDE.md)", rules_section])

    parts.extend(
        [
            "",
            "## Output Format",
            "Respond ONLY with valid JSON matching this schema (no markdown fences):",
            json.dumps(_response_schema(), indent=2),
        ]
    )

    return "\n".join(parts)


def _format_rubric(rubric: list[RubricDimension]) -> str:
    """Format rubric dimensions into readable text for the prompt."""
    lines: list[str] = []
    for dim in rubric:
        lines.append(f"### {dim.name} (weight: {dim.weight})")
        lines.append(dim.description)
        for criterion in dim.criteria:
            lines.append(f"  - {criterion}")
        lines.append("")
    return "\n".join(lines)


def _format_rules(rules: list[Rule]) -> str:
    """Format CLAUDE.md rules into readable text for the prompt."""
    lines: list[str] = []
    for rule in rules:
        lines.append(f"- **{rule.id}** [{rule.category}]: {rule.description}")
        if rule.do_example:
            lines.append(f"  DO: `{rule.do_example[:120]}`")
        if rule.dont_example:
            lines.append(f"  DON'T: `{rule.dont_example[:120]}`")
    return "\n".join(lines)


def _response_schema() -> dict:
    """Return the expected JSON response schema for documentation in the prompt."""
    return {
        "dimensions": [
            {
                "name": "<dimension_name>",
                "score": 0.85,
                "reasoning": "<explanation>",
            }
        ],
        "summary": "<overall assessment>",
        "rule_adherence_notes": ["<note about rule compliance or violation>"],
    }


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_llm_response(
    raw_text: str,
    rubric: list[RubricDimension],
) -> LLMJudgeResult:
    """Parse the LLM's JSON response into a structured result.

    Args:
        raw_text: Raw text response from the LLM (expected to be JSON).
        rubric: The rubric used, for weight lookup.

    Returns:
        Populated LLMJudgeResult.

    Raises:
        ValueError: If the response is not valid JSON or is missing required fields.
    """
    # Strip markdown fences if the model wrapped its output
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        cleaned = cleaned[first_newline + 1 : last_fence].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        msg = f"LLM response is not valid JSON: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(data, dict):
        msg = f"Expected a JSON object, got {type(data).__name__}"
        raise ValueError(msg)

    if "dimensions" not in data:
        msg = "LLM response missing required 'dimensions' key"
        raise ValueError(msg)

    weight_lookup = {dim.name: dim.weight for dim in rubric}

    dimension_scores: list[DimensionScore] = []
    for dim_data in data["dimensions"]:
        name = str(dim_data.get("name", "unknown"))
        raw_score = float(dim_data.get("score", 0.0))
        score = max(0.0, min(1.0, raw_score))
        reasoning = str(dim_data.get("reasoning", ""))
        weight = weight_lookup.get(name, 0.0)
        dimension_scores.append(
            DimensionScore(name=name, score=score, weight=weight, reasoning=reasoning)
        )

    overall_score = _compute_weighted_score(dimension_scores)
    summary = str(data.get("summary", ""))
    rule_notes = [str(n) for n in data.get("rule_adherence_notes", [])]

    return LLMJudgeResult(
        dimensions=dimension_scores,
        overall_score=overall_score,
        summary=summary,
        rule_adherence_notes=rule_notes,
    )


def _compute_weighted_score(dimensions: list[DimensionScore]) -> float:
    """Compute the weighted average score across dimensions.

    Args:
        dimensions: Scored dimensions with weights.

    Returns:
        Weighted average, or 0.0 if total weight is zero.
    """
    total_weight = sum(d.weight for d in dimensions)
    if total_weight == 0.0:
        return 0.0
    return sum(d.score * d.weight for d in dimensions) / total_weight


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------


async def evaluate_with_llm(
    code: str,
    problem_prompt: str,
    rules: list[Rule],
    rubric: list[RubricDimension],
    reference_solution: str | None = None,
) -> LLMJudgeResult:
    """Evaluate code using Claude as an LLM judge.

    Constructs a prompt asking Claude to score the code on each rubric
    dimension, calls the Anthropic API, and parses the structured JSON
    response.

    Args:
        code: The source code to evaluate.
        problem_prompt: Description of the problem the code solves.
        rules: CLAUDE.md rules for rule-adherence evaluation.
        rubric: Rubric dimensions to score against.
        reference_solution: Optional known-good solution for comparison.

    Returns:
        LLMJudgeResult with per-dimension scores and overall assessment.
        If the API key is missing, returns a zeroed-out result with a
        skip note instead of raising.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping LLM evaluation")
        return _skipped_result(rubric)

    prompt = build_evaluation_prompt(
        code=code,
        problem_prompt=problem_prompt,
        rules=rules,
        rubric=rubric,
        reference_solution=reference_solution,
    )

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = message.content[0].text
        logger.info("Received LLM judge response (%d chars)", len(raw_text))

    except ImportError:
        logger.error("anthropic package not installed")
        return _skipped_result(rubric, note="anthropic package not installed")
    except Exception:
        logger.exception("Anthropic API call failed")
        return _skipped_result(rubric, note="Anthropic API call failed")

    try:
        return parse_llm_response(raw_text, rubric)
    except ValueError:
        logger.exception("Failed to parse LLM judge response")
        return _skipped_result(rubric, note="Malformed LLM response")


def _skipped_result(
    rubric: list[RubricDimension],
    note: str = "LLM evaluation skipped — ANTHROPIC_API_KEY not set",
) -> LLMJudgeResult:
    """Build a zeroed-out result when LLM evaluation cannot run.

    Args:
        rubric: The rubric to use for dimension names/weights.
        note: Explanation of why evaluation was skipped.

    Returns:
        LLMJudgeResult with all scores at 0.0.
    """
    dimensions = [
        DimensionScore(
            name=dim.name,
            score=0.0,
            weight=dim.weight,
            reasoning="Evaluation skipped",
        )
        for dim in rubric
    ]
    return LLMJudgeResult(
        dimensions=dimensions,
        overall_score=0.0,
        summary="LLM evaluation was not performed.",
        rule_adherence_notes=[note],
    )

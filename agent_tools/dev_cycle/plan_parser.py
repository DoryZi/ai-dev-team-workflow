"""Parse plan markdown files into structured data.

Plans follow a convention:
- ``## Acceptance Criteria`` section with bullet-point criteria
- ``## Step N — Title`` sections with description, optional file lists,
  and optional test classification

Usage:
    from plan_parser import parse_plan
    plan = parse_plan(Path("plans/my-feature-2026-04-01.md"))
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches "## Step 1 — Title" or "## Step 1: Title" or "## Step 1 - Title"
_STEP_HEADER_RE = re.compile(
    r"^##\s+Step\s+(\d+)\s*[:\-—–]\s*(.+)$", re.MULTILINE
)

# Matches bullet-point file paths (lines starting with "- `path`" or "- path")
_FILE_BULLET_RE = re.compile(r"^\s*[-*]\s+`?([^\s`]+\.(?:py|md|toml|yaml|yml|json|sh))`?")

# Matches "Test classification: unit" or similar
_TEST_CLASS_RE = re.compile(r"test\s+classification\s*:\s*(.+)", re.IGNORECASE)


@dataclass
class PlanStep:
    """A single step in an implementation plan.

    Attributes:
        number: Step number (1-based).
        title: Short description of the step.
        description: Full markdown text of the step body.
        files: List of file paths mentioned in the step (may be empty
            for high-level plans where SDE decides file structure).
        test_classification: Type of tests needed — "unit", "e2e", or "both".
        acceptance_criteria: ACs this step addresses (extracted from step body).
    """

    number: int = 0
    title: str = ""
    description: str = ""
    files: list[str] = field(default_factory=list)
    test_classification: str = "unit"
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """A parsed implementation plan.

    Attributes:
        title: Plan title (first H1 header, or filename).
        steps: Ordered list of implementation steps.
        acceptance_criteria: Top-level acceptance criteria for the feature.
        raw_text: The original markdown text of the plan.
    """

    title: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    raw_text: str = ""


def parse_plan(path: Path) -> Plan:
    """Parse a plan markdown file into a Plan object.

    Args:
        path: Path to the plan markdown file.

    Returns:
        Parsed Plan with steps, acceptance criteria, and raw text.

    Raises:
        FileNotFoundError: If the plan file does not exist.
        ValueError: If the plan has no steps.
    """
    content = path.read_text(encoding="utf-8")

    plan = Plan(raw_text=content)

    # Extract title from first H1
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        plan.title = title_match.group(1).strip()
    else:
        plan.title = path.stem

    # Extract top-level acceptance criteria
    plan.acceptance_criteria = _extract_acceptance_criteria(content)

    # Extract steps
    plan.steps = _extract_steps(content)

    if not plan.steps:
        raise ValueError(f"Plan has no steps: {path}")

    logger.info(
        "Parsed plan: %s (%d steps, %d ACs)",
        plan.title,
        len(plan.steps),
        len(plan.acceptance_criteria),
    )

    return plan


def _extract_acceptance_criteria(content: str) -> list[str]:
    """Extract acceptance criteria from the plan markdown.

    Looks for a ``## Acceptance Criteria`` section and pulls bullet items.

    Args:
        content: Full plan markdown text.

    Returns:
        List of acceptance criterion strings.
    """
    ac_match = re.search(
        r"^##\s+Acceptance\s+Criteria\b.*?\n(.*?)(?=^##\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not ac_match:
        return []

    ac_section = ac_match.group(1)
    criteria = []

    for line in ac_section.splitlines():
        stripped = line.strip()
        # Match "- [ ] criterion" or "- criterion" or "* criterion"
        bullet_match = re.match(r"^[-*]\s+(?:\[.\]\s+)?(.+)$", stripped)
        if bullet_match:
            criteria.append(bullet_match.group(1).strip())

    return criteria


def _extract_steps(content: str) -> list[PlanStep]:
    """Extract numbered steps from the plan markdown.

    Args:
        content: Full plan markdown text.

    Returns:
        Ordered list of PlanStep objects.
    """
    matches = list(_STEP_HEADER_RE.finditer(content))
    if not matches:
        return []

    steps = []
    for i, match in enumerate(matches):
        step_number = int(match.group(1))
        step_title = match.group(2).strip()

        # Extract body: from after this header to the next step header (or end)
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()

        step = PlanStep(
            number=step_number,
            title=step_title,
            description=body,
            files=_extract_files(body),
            test_classification=_extract_test_classification(body),
            acceptance_criteria=_extract_step_acs(body),
        )

        steps.append(step)

    return steps


def _extract_files(body: str) -> list[str]:
    """Extract file paths from a step body.

    Looks for bullet-point file paths. Returns empty list if no files
    are mentioned (high-level plans).

    Args:
        body: Step body markdown text.

    Returns:
        List of file path strings.
    """
    files = []
    for line in body.splitlines():
        file_match = _FILE_BULLET_RE.match(line)
        if file_match:
            files.append(file_match.group(1))
    return files


def _extract_test_classification(body: str) -> str:
    """Extract test classification from a step body.

    Args:
        body: Step body markdown text.

    Returns:
        Test classification string — "unit", "e2e", or "both".
        Defaults to "unit" if not specified.
    """
    match = _TEST_CLASS_RE.search(body)
    if match:
        classification = match.group(1).strip().lower()
        if classification in ("unit", "e2e", "both"):
            return classification
    return "unit"


def _extract_step_acs(body: str) -> list[str]:
    """Extract acceptance criteria references from a step body.

    Looks for lines like "- AC: criterion text" or "Addresses AC 1, 3".

    Args:
        body: Step body markdown text.

    Returns:
        List of AC reference strings.
    """
    acs = []
    for line in body.splitlines():
        stripped = line.strip()
        ac_match = re.match(r"^[-*]\s+AC\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if ac_match:
            acs.append(ac_match.group(1).strip())
    return acs

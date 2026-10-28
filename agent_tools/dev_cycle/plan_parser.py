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
_FILE_BULLET_RE = re.compile(r"^\s*[-*]\s+`?([^\s`(]+[^\s`)\s])`?")

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
        raw = match.group(1).strip().lower()
        # Take first word only — handles "e2e (build + run + curl test)"
        first_word = raw.split()[0] if raw else ""
        # Also handle "unit + e2e" as "both"
        if "unit" in raw and "e2e" in raw:
            return "both"
        if first_word in ("unit", "e2e", "both"):
            return first_word
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


def _dir_prefix(filepath: str, depth: int = 2) -> str:
    """Extract the first N path components as a directory prefix.

    Args:
        filepath: A relative file path string.
        depth: Number of leading components to use.

    Returns:
        The prefix string, or the full path if fewer than depth components.
    """
    parts = Path(filepath).parts
    return str(Path(*parts[:depth])) if len(parts) >= depth else filepath


def get_parallel_groups(
    steps: list[PlanStep], max_parallel: int = 4,
) -> list[list[PlanStep]]:
    """Group steps into sequential batches of independent parallel work.

    A step creates a dependency barrier if it contains foundation files
    (__init__.py, models.py, pyproject.toml) or if it has more than one
    file (aggregator steps that import from multiple modules).

    Groups are capped at ``max_parallel`` to avoid API rate limits.

    Args:
        steps: Ordered list of plan steps.
        max_parallel: Maximum steps per parallel group (default 4).

    Returns:
        Ordered list of groups. Each group is a list of independent steps.
    """
    if not steps:
        return []

    _FOUNDATION_NAMES = {"__init__.py", "models.py", "pyproject.toml"}

    def _is_barrier(step: PlanStep) -> bool:
        """A step is a barrier if it creates foundation files or aggregates."""
        files = step.files or []
        has_foundation = any(Path(f).name in _FOUNDATION_NAMES for f in files)
        return has_foundation

    groups: list[list[PlanStep]] = []
    current_group: list[PlanStep] = []

    for step in steps:
        if _is_barrier(step):
            if current_group:
                groups.append(current_group)
                current_group = []
            groups.append([step])
        else:
            current_group.append(step)
            if len(current_group) >= max_parallel:
                groups.append(current_group)
                current_group = []

    if current_group:
        groups.append(current_group)

    return groups


# Non-Python file extensions that indicate infrastructure/config steps
_NON_PYTHON_EXTENSIONS = frozenset({
    ".html", ".css", ".js", ".json", ".yaml", ".yml", ".toml",
    ".md", ".rst", ".txt", ".cfg", ".ini", ".sh", ".bash",
    ".dockerfile", ".dockerignore", ".env", ".sql", ".xml",
    ".csv", ".lock",
})


def _is_python_file(filepath: str) -> bool:
    """Check whether a file path refers to a Python file.

    Args:
        filepath: Relative file path string.

    Returns:
        True if the file has a .py or .pyi extension.
    """
    suffix = Path(filepath).suffix.lower()
    return suffix in (".py", ".pyi")


def is_non_python_step(step: PlanStep) -> bool:
    """Check whether all files in a step are non-Python.

    Args:
        step: The plan step to check.

    Returns:
        True if the step has files and none are Python files.
    """
    if not step.files:
        return False
    return all(not _is_python_file(f) for f in step.files)

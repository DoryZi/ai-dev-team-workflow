"""Load project convention files for agent context.

Reads and concatenates convention documents so agents have the project's
coding rules and workflow contract in their prompt context.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_FILES = [
    "CLAUDE.md",
    "conventions/workflow-contract.md",
    "conventions/python-coding.md",
]


def get_conventions_for_step(
    step_files: list[str], repo_root: Path
) -> str:
    """Load and concatenate convention files for a plan step.

    Args:
        step_files: List of file paths the step touches (currently unused
            but kept for future domain-specific convention loading).
        repo_root: Path to the repository root directory.

    Returns:
        Concatenated convention text with section headers.
    """
    return _load_base_conventions(repo_root)


def get_conventions_header(repo_root: Path) -> str:
    """Load base conventions for agents without step context.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Concatenated base convention text.
    """
    return _load_base_conventions(repo_root)


def _load_base_conventions(repo_root: Path) -> str:
    """Load and concatenate the base convention files.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Concatenated text with section headers for each file.
    """
    repo_root = Path(repo_root)
    sections: list[str] = []

    for relative_path in _BASE_FILES:
        full_path = repo_root / relative_path
        try:
            content = full_path.read_text(encoding="utf-8")
            sections.append(f"# --- {relative_path} ---\n\n{content}")
        except FileNotFoundError:
            logger.warning("Convention file not found: %s", full_path)
        except OSError as exc:
            logger.warning("Could not read %s: %s", full_path, exc)

    return "\n\n".join(sections)

"""Shared fixtures for task_tracker tests."""

import json
from pathlib import Path

import pytest

SAMPLE_TASKS: list[dict] = [
    {"id": 1, "title": "Buy groceries", "done": False},
    {"id": 2, "title": "Write tests", "done": False},
    {"id": 3, "title": "Ship feature", "done": True},
]


@pytest.fixture()
def task_store(tmp_path: Path) -> Path:
    """Create a temporary JSON store pre-populated with sample tasks.

    Returns:
        Path to the temporary tasks.json file containing SAMPLE_TASKS.
    """
    store = tmp_path / "tasks.json"
    store.write_text(json.dumps(SAMPLE_TASKS, indent=2) + "\n")
    return store

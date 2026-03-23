"""Tests for the delete_task feature in tracker module."""

import json
from pathlib import Path

import pytest

from tracker import delete_task, load_tasks

from .conftest import SAMPLE_TASKS


class TestDeleteTaskRemovesFromStore:
    """Verify that delete_task physically removes the task from the JSON file."""

    def test_delete_task_removes_from_store(self, task_store: Path) -> None:
        """Should remove the specified task from the persisted JSON file."""
        delete_task(1, store=task_store)

        remaining = load_tasks(task_store)
        remaining_ids = [t["id"] for t in remaining]
        assert 1 not in remaining_ids
        assert len(remaining) == len(SAMPLE_TASKS) - 1


class TestDeleteTaskReturnValue:
    """Verify that delete_task returns the correct deleted task dict."""

    def test_delete_task_returns_deleted_task(self, task_store: Path) -> None:
        """Should return the full task dict of the deleted task."""
        result = delete_task(2, store=task_store)

        assert result["id"] == 2
        assert result["title"] == "Write tests"
        assert result["done"] is False

    def test_delete_task_completed_task_succeeds(self, task_store: Path) -> None:
        """Should successfully delete a task that has done=True."""
        result = delete_task(3, store=task_store)

        assert result["id"] == 3
        assert result["done"] is True

        remaining = load_tasks(task_store)
        assert all(t["id"] != 3 for t in remaining)


class TestDeleteTaskErrors:
    """Verify that delete_task raises KeyError for invalid IDs."""

    def test_delete_task_nonexistent_id_raises_key_error(
        self, task_store: Path
    ) -> None:
        """Should raise KeyError when the task ID does not exist."""
        with pytest.raises(KeyError, match="Task 999 not found"):
            delete_task(999, store=task_store)

    def test_delete_task_empty_store_raises_key_error(self, tmp_path: Path) -> None:
        """Should raise KeyError when the store file does not exist."""
        missing_store = tmp_path / "nonexistent.json"

        with pytest.raises(KeyError, match="Task 1 not found"):
            delete_task(1, store=missing_store)


class TestDeleteTaskPreservesOtherTasks:
    """Verify that delete_task leaves other tasks untouched."""

    def test_delete_task_preserves_other_tasks(self, task_store: Path) -> None:
        """Should not modify any task other than the one being deleted."""
        delete_task(2, store=task_store)

        remaining = load_tasks(task_store)
        assert len(remaining) == 2

        task_1 = next(t for t in remaining if t["id"] == 1)
        assert task_1["title"] == "Buy groceries"
        assert task_1["done"] is False

        task_3 = next(t for t in remaining if t["id"] == 3)
        assert task_3["title"] == "Ship feature"
        assert task_3["done"] is True


class TestDeleteTaskLastTask:
    """Verify edge case of deleting the only task in the store."""

    def test_delete_task_last_task_leaves_empty_list(self, tmp_path: Path) -> None:
        """Should result in an empty list when the only task is deleted."""
        store = tmp_path / "tasks.json"
        single_task = [{"id": 1, "title": "Only task", "done": False}]
        store.write_text(json.dumps(single_task, indent=2) + "\n")

        result = delete_task(1, store=store)

        assert result["id"] == 1
        remaining = load_tasks(store)
        assert remaining == []

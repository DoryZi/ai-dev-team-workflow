"""Tests for the Task Manager problem."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from solution import Task, TaskManager


@pytest.fixture
def storage_path(tmp_path: Path) -> str:
    """Return a path to a non-existent JSON file for testing."""
    return str(tmp_path / "tasks.json")


@pytest.fixture
def manager(storage_path: str) -> TaskManager:
    """Create a fresh TaskManager with an empty storage file."""
    return TaskManager(storage_path)


class TestTaskManagerAdd:
    """Tests for adding tasks."""

    def test_add_task(self, manager: TaskManager) -> None:
        task = manager.add("Buy groceries")
        assert task.title == "Buy groceries"
        assert task.id == 1
        assert task.done is False

    def test_add_multiple_tasks_auto_increments_id(self, manager: TaskManager) -> None:
        t1 = manager.add("Task one")
        t2 = manager.add("Task two")
        t3 = manager.add("Task three")
        assert t1.id == 1
        assert t2.id == 2
        assert t3.id == 3

    def test_add_task_strips_whitespace(self, manager: TaskManager) -> None:
        task = manager.add("  trimmed title  ")
        assert task.title == "trimmed title"

    def test_add_empty_title_raises(self, manager: TaskManager) -> None:
        with pytest.raises(ValueError):
            manager.add("")

    def test_add_whitespace_only_title_raises(self, manager: TaskManager) -> None:
        with pytest.raises(ValueError):
            manager.add("   ")


class TestTaskManagerGet:
    """Tests for retrieving tasks."""

    def test_get_existing_task(self, manager: TaskManager) -> None:
        added = manager.add("Test task")
        retrieved = manager.get(added.id)
        assert retrieved.title == "Test task"
        assert retrieved.id == added.id

    def test_get_nonexistent_task_raises(self, manager: TaskManager) -> None:
        with pytest.raises(KeyError):
            manager.get(999)


class TestTaskManagerListAll:
    """Tests for listing tasks."""

    def test_list_empty(self, manager: TaskManager) -> None:
        assert manager.list_all() == []

    def test_list_returns_sorted_by_id(self, manager: TaskManager) -> None:
        manager.add("Third")
        manager.add("First")
        manager.add("Second")
        tasks = manager.list_all()
        assert [t.id for t in tasks] == [1, 2, 3]


class TestTaskManagerComplete:
    """Tests for completing tasks."""

    def test_complete_task(self, manager: TaskManager) -> None:
        task = manager.add("Do laundry")
        completed = manager.complete(task.id)
        assert completed.done is True

    def test_complete_nonexistent_raises(self, manager: TaskManager) -> None:
        with pytest.raises(KeyError):
            manager.complete(999)


class TestTaskManagerDelete:
    """Tests for deleting tasks."""

    def test_delete_task(self, manager: TaskManager) -> None:
        task = manager.add("Temporary")
        manager.delete(task.id)
        with pytest.raises(KeyError):
            manager.get(task.id)

    def test_delete_nonexistent_raises(self, manager: TaskManager) -> None:
        with pytest.raises(KeyError):
            manager.delete(999)

    def test_id_increments_after_delete(self, manager: TaskManager) -> None:
        t1 = manager.add("First")
        manager.delete(t1.id)
        t2 = manager.add("Second")
        assert t2.id == 2  # Should not reuse ID 1


class TestTaskManagerUpdate:
    """Tests for updating tasks."""

    def test_update_title(self, manager: TaskManager) -> None:
        task = manager.add("Old title")
        updated = manager.update(task.id, "New title")
        assert updated.title == "New title"

    def test_update_nonexistent_raises(self, manager: TaskManager) -> None:
        with pytest.raises(KeyError):
            manager.update(999, "New title")

    def test_update_empty_title_raises(self, manager: TaskManager) -> None:
        task = manager.add("Valid")
        with pytest.raises(ValueError):
            manager.update(task.id, "")


class TestTaskManagerPersistence:
    """Tests for JSON file persistence."""

    def test_tasks_persisted_to_file(self, manager: TaskManager, storage_path: str) -> None:
        manager.add("Persisted task")
        data = json.loads(Path(storage_path).read_text())
        assert len(data) == 1
        assert data[0]["title"] == "Persisted task"

    def test_tasks_loaded_from_file(self, storage_path: str) -> None:
        # Create a manager, add tasks, then create a new manager from the same file
        m1 = TaskManager(storage_path)
        m1.add("Surviving task")
        m1.add("Another task")

        m2 = TaskManager(storage_path)
        tasks = m2.list_all()
        assert len(tasks) == 2
        assert tasks[0].title == "Surviving task"

    def test_new_ids_after_reload(self, storage_path: str) -> None:
        m1 = TaskManager(storage_path)
        m1.add("First")
        m1.add("Second")

        m2 = TaskManager(storage_path)
        t3 = m2.add("Third")
        assert t3.id == 3  # Should continue from max existing ID

    def test_nonexistent_file_starts_empty(self, storage_path: str) -> None:
        manager = TaskManager(storage_path)
        assert manager.list_all() == []

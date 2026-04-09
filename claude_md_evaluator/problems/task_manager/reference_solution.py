"""Reference solution for the Task Manager problem."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """A single task.

    Attributes:
        id: Unique auto-incremented identifier.
        title: Short description of the task.
        done: Whether the task is completed.
    """

    id: int
    title: str
    done: bool = False


class TaskManager:
    """Manages tasks with CRUD operations and JSON file persistence.

    Attributes:
        storage_path: Path to the JSON file used for persistence.
    """

    def __init__(self, storage_path: str) -> None:
        """Initialize the task manager with a path to the JSON storage file.

        If the file exists, load tasks from it. If it does not exist, start
        with an empty task list.

        Args:
            storage_path: Path to the JSON file used for persistence.
        """
        self.storage_path = Path(storage_path)
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self._load()

    def _load(self) -> None:
        """Load tasks from the JSON storage file.

        If the file does not exist or is empty, initialize with an empty task list.
        """
        if not self.storage_path.is_file():
            return

        content = self.storage_path.read_text(encoding="utf-8").strip()
        if not content:
            return

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in storage file: %s", exc)
            raise

        for item in data:
            task = Task(id=item["id"], title=item["title"], done=item["done"])
            self._tasks[task.id] = task

        if self._tasks:
            self._next_id = max(self._tasks) + 1

    def _save(self) -> None:
        """Persist current tasks to the JSON storage file."""
        data = [asdict(task) for task in sorted(self._tasks.values(), key=lambda t: t.id)]
        self.storage_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _validate_title(self, title: str) -> str:
        """Validate and strip a task title.

        Args:
            title: The raw title string.

        Returns:
            The stripped title.

        Raises:
            ValueError: If the title is empty or whitespace-only.
        """
        stripped = title.strip()
        if not stripped:
            raise ValueError("Task title cannot be empty")
        return stripped

    def add(self, title: str) -> Task:
        """Add a new task with the given title.

        Args:
            title: Short description of the task.

        Returns:
            The newly created Task.

        Raises:
            ValueError: If title is empty or whitespace-only.
        """
        clean_title = self._validate_title(title)
        task = Task(id=self._next_id, title=clean_title)
        self._tasks[task.id] = task
        self._next_id += 1
        self._save()
        return task

    def get(self, task_id: int) -> Task:
        """Retrieve a task by its ID.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            The Task with the given ID.

        Raises:
            KeyError: If no task with the given ID exists.
        """
        if task_id not in self._tasks:
            raise KeyError(f"No task with ID {task_id}")
        return self._tasks[task_id]

    def list_all(self) -> list[Task]:
        """Return all tasks, sorted by ID.

        Returns:
            List of all tasks.
        """
        return sorted(self._tasks.values(), key=lambda t: t.id)

    def complete(self, task_id: int) -> Task:
        """Mark a task as done.

        Args:
            task_id: The ID of the task to complete.

        Returns:
            The updated Task.

        Raises:
            KeyError: If no task with the given ID exists.
        """
        task = self.get(task_id)
        task.done = True
        self._save()
        return task

    def delete(self, task_id: int) -> None:
        """Delete a task by its ID.

        Args:
            task_id: The ID of the task to delete.

        Raises:
            KeyError: If no task with the given ID exists.
        """
        if task_id not in self._tasks:
            raise KeyError(f"No task with ID {task_id}")
        del self._tasks[task_id]
        self._save()

    def update(self, task_id: int, title: str) -> Task:
        """Update a task's title.

        Args:
            task_id: The ID of the task to update.
            title: The new title for the task.

        Returns:
            The updated Task.

        Raises:
            KeyError: If no task with the given ID exists.
            ValueError: If title is empty or whitespace-only.
        """
        clean_title = self._validate_title(title)
        task = self.get(task_id)
        task.title = clean_title
        self._save()
        return task

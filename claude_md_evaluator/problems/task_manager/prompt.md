# Task Manager

## Task

Implement a task manager that supports CRUD operations on tasks with persistence to a JSON file on disk.

## Requirements

Create a file named `solution.py` containing the following:

```python
from dataclasses import dataclass


@dataclass
class Task:
    """A single task."""
    id: int
    title: str
    done: bool = False


class TaskManager:
    def __init__(self, storage_path: str) -> None:
        """Initialize the task manager with a path to the JSON storage file.

        If the file exists, load tasks from it. If it does not exist, start
        with an empty task list (the file will be created on the first write).

        Args:
            storage_path: Path to the JSON file used for persistence.
        """

    def add(self, title: str) -> Task:
        """Add a new task with the given title.

        The task gets an auto-incremented ID (starting from 1).
        The task list is persisted to disk after adding.

        Args:
            title: Short description of the task.

        Returns:
            The newly created Task.

        Raises:
            ValueError: If title is empty or whitespace-only.
        """

    def get(self, task_id: int) -> Task:
        """Retrieve a task by its ID.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            The Task with the given ID.

        Raises:
            KeyError: If no task with the given ID exists.
        """

    def list_all(self) -> list[Task]:
        """Return all tasks, sorted by ID.

        Returns:
            List of all tasks.
        """

    def complete(self, task_id: int) -> Task:
        """Mark a task as done.

        Args:
            task_id: The ID of the task to complete.

        Returns:
            The updated Task.

        Raises:
            KeyError: If no task with the given ID exists.
        """

    def delete(self, task_id: int) -> None:
        """Delete a task by its ID.

        Args:
            task_id: The ID of the task to delete.

        Raises:
            KeyError: If no task with the given ID exists.
        """

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
```

## Constraints

- Use `pathlib.Path` for all file system operations.
- JSON file format: a list of objects, each with `id`, `title`, and `done` fields.
- IDs are auto-incremented: each new task gets `max(existing_ids) + 1`, or 1 if no tasks exist.
- All mutating operations (`add`, `complete`, `delete`, `update`) must persist changes to the JSON file immediately.
- The storage file must be valid JSON at all times.

## Edge Cases

- Storage file does not exist yet (first use).
- Storage file exists but is empty (treat as no tasks).
- Deleting the only task.
- Adding a task after deleting all tasks (ID should still increment).
- Title with leading/trailing whitespace should be stripped.
- Loading tasks from a previously saved file (persistence round-trip).

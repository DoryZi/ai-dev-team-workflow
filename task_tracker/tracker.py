"""Simple CLI task tracker backed by a JSON file.

Supports adding, listing, completing, and deleting tasks.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STORE = Path("tasks.json")


def load_tasks(store: Path = DEFAULT_STORE) -> list[dict]:
    """Load tasks from the JSON store.

    Args:
        store: Path to the JSON file.

    Returns:
        List of task dictionaries.
    """
    if not store.exists():
        return []
    data = json.loads(store.read_text())
    return data


def save_tasks(tasks: list[dict], store: Path = DEFAULT_STORE) -> None:
    """Save tasks to the JSON store.

    Args:
        tasks: List of task dictionaries.
        store: Path to the JSON file.
    """
    store.write_text(json.dumps(tasks, indent=2) + "\n")


def next_id(tasks: list[dict]) -> int:
    """Return the next available task ID.

    Args:
        tasks: Existing task list.

    Returns:
        Integer ID one higher than the current max, or 1 if empty.
    """
    if not tasks:
        return 1
    return max(t["id"] for t in tasks) + 1


def add_task(title: str, store: Path = DEFAULT_STORE) -> dict:
    """Add a new task.

    Args:
        title: Short description of the task.
        store: Path to the JSON file.

    Returns:
        The newly created task dictionary.

    Raises:
        ValueError: If title is empty or whitespace-only.
    """
    if not title.strip():
        raise ValueError("Title cannot be empty")

    tasks = load_tasks(store)
    task = {
        "id": next_id(tasks),
        "title": title.strip(),
        "done": False,
    }
    tasks.append(task)
    save_tasks(tasks, store)
    logger.info("Added task", extra={"id": task["id"], "title": task["title"]})
    return task


def list_tasks(show_all: bool = False, store: Path = DEFAULT_STORE) -> list[dict]:
    """List tasks, optionally including completed ones.

    Args:
        show_all: If True, include completed tasks.
        store: Path to the JSON file.

    Returns:
        Filtered list of task dictionaries.
    """
    tasks = load_tasks(store)
    if show_all:
        return tasks
    return [t for t in tasks if not t["done"]]


def complete_task(task_id: int, store: Path = DEFAULT_STORE) -> dict:
    """Mark a task as done.

    Args:
        task_id: ID of the task to complete.
        store: Path to the JSON file.

    Returns:
        The updated task dictionary.

    Raises:
        KeyError: If no task with the given ID exists.
    """
    tasks = load_tasks(store)
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            save_tasks(tasks, store)
            logger.info("Completed task", extra={"id": task_id})
            return task
    raise KeyError(f"Task {task_id} not found")


def delete_task(task_id: int, store: Path = DEFAULT_STORE) -> dict:
    """Delete a task by ID.

    Args:
        task_id: ID of the task to delete.
        store: Path to the JSON file.

    Returns:
        The deleted task dictionary.

    Raises:
        KeyError: If no task with the given ID exists.
    """
    tasks = load_tasks(store)
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            deleted = tasks.pop(i)
            save_tasks(tasks, store)
            logger.info("Deleted task", extra={"id": task_id})
            return deleted
    raise KeyError(f"Task {task_id} not found")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Simple task tracker")
    sub = parser.add_subparsers(dest="command")

    add_parser = sub.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", nargs="+", help="Task title")

    list_parser = sub.add_parser("list", help="List tasks")
    list_parser.add_argument("-a", "--all", action="store_true", help="Include completed")

    done_parser = sub.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("id", type=int, help="Task ID")

    delete_parser = sub.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("id", type=int, help="Task ID")

    args = parser.parse_args()

    if args.command == "add":
        title = " ".join(args.title)
        task = add_task(title)
        print(f"Added: [{task['id']}] {task['title']}")

    elif args.command == "list":
        tasks = list_tasks(show_all=args.all)
        if not tasks:
            print("No tasks.")
            return
        for t in tasks:
            status = "x" if t["done"] else " "
            print(f"[{status}] {t['id']}: {t['title']}")

    elif args.command == "done":
        try:
            task = complete_task(args.id)
            print(f"Done: [{task['id']}] {task['title']}")
        except KeyError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    elif args.command == "delete":
        try:
            task = delete_task(args.id)
            print(f"Deleted: [{task['id']}] {task['title']}")
        except KeyError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

# CLAUDE.md — AI Dev Team Workflow

Multi-agent Python development with Claude Code.

## Project Structure

```
task_tracker/              ← sample app (the code being developed)
├── pyproject.toml
├── tracker.py
└── tests/
.claude/
├── agents/                ← sde, test-eng, code-reviewer
└── skills/                ← dev-tdd, dev-fast, run-tests, python-reviewer, review
conventions/
└── python-coding.md       ← full coding standards (agents reference this)
```

## Execution Rules

1. **Always use `uv run --directory`** to run scripts
2. **If a tool fails, fix the tool** — don't work around it

**DO:**
```bash
uv run --directory task_tracker python tracker.py
uv add --directory task_tracker some-package
```

**DON'T:**
```bash
python3 tracker.py              # system python
source venv/bin/activate        # venv
pip install some-package        # system pip
```

## Code Boundaries

### Type hints — always

**DO:**
```python
def add_task(title: str, priority: int = 1) -> Task:
    ...
```

**DON'T:**
```python
def add_task(title, priority=1):
    ...
```

### Docstrings — on all public functions

**DO:**
```python
def add_task(title: str, priority: int = 1) -> Task:
    """Create a new task with the given title.

    Args:
        title: Short description of the task.
        priority: Importance level (1=low, 3=high).

    Returns:
        The newly created Task.

    Raises:
        ValueError: If title is empty.
    """
```

**DON'T:**
```python
def add_task(title: str, priority: int = 1) -> Task:
    """Add task."""  # vague, no args/returns
```

### Error handling — specific, never silent

**DO:**
```python
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    logger.error("Invalid JSON", extra={"error": str(e)})
    raise
```

**DON'T:**
```python
try:
    data = json.loads(raw)
except:
    pass  # silent failure hides bugs
```

### DRY — extract shared logic

**DO:**
```python
def validate_task(title: str) -> None:
    if not title.strip():
        raise ValueError("Title cannot be empty")

def add_task(title: str) -> Task:
    validate_task(title)
    ...

def update_task(task_id: int, title: str) -> Task:
    validate_task(title)
    ...
```

**DON'T:**
```python
def add_task(title: str) -> Task:
    if not title.strip():
        raise ValueError("Title cannot be empty")
    ...

def update_task(task_id: int, title: str) -> Task:
    if not title.strip():
        raise ValueError("Title cannot be empty")  # duplicated
    ...
```

### File size — keep it small

| Scope | Max Lines |
|-------|-----------|
| Function | 50 |
| Class | 300 |
| File | 500 |

Split modules and extract helpers when limits are hit.

### Imports — top of file, grouped

**DO:**
```python
# stdlib
import json
import logging
from pathlib import Path

# third-party
from pydantic import BaseModel

# local
from .utils import validate_task
```

**DON'T:**
```python
def add_task(title: str) -> Task:
    import json          # buried inside function
    from pathlib import Path  # import should be at top
    ...

from pydantic import *  # wildcard imports
import os, sys, json     # multi-import on one line
```

### Paths — use pathlib

**DO:**
```python
from pathlib import Path
output = data_dir / "tasks.json"
```

**DON'T:**
```python
output = os.path.join(data_dir, "tasks.json")
```

## Full Standards

See `conventions/python-coding.md` for complete coding conventions (naming, imports, logging, testing, secrets).

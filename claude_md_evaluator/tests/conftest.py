"""Shared fixtures for claude_md_evaluator tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_claude_md(tmp_path: Path) -> Path:
    """Create a temporary CLAUDE.md file for testing."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("""# Test CLAUDE.md

## Code Boundaries

### Type hints — always

**DO:**
```python
def add_task(title: str, priority: int = 1) -> Task:
    ...
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
""")
    return claude_md


@pytest.fixture
def sample_problem_set() -> list[str]:
    """Sample problem set names for testing."""
    return ["lru_cache", "csv_parser"]


@pytest.fixture
def multiple_claude_md_files(tmp_path: Path) -> list[Path]:
    """Create multiple CLAUDE.md files for testing."""
    files = []
    for i in range(3):
        claude_md = tmp_path / f"CLAUDE-{i}.md"
        claude_md.write_text(f"# Test CLAUDE.md {i}\n\nSample content for test file {i}.")
        files.append(claude_md)
    return files
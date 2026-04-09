"""Tests for the CLAUDE.md rule parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from evaluator.rule_parser import (
    VALID_CATEGORIES,
    VALID_CHECK_TYPES,
    Rule,
    parse_claude_md,
    parse_claude_md_text,
)

# ---------------------------------------------------------------------------
# Fixtures / sample content
# ---------------------------------------------------------------------------

SAMPLE_CLAUDE_MD = """\
# CLAUDE.md — Sample Project

## Execution Rules

1. **Always use `uv run --directory`** to run scripts

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
    \"\"\"Create a new task.

    Args:
        title: Short description of the task.
    \"\"\"
```

**DON'T:**
```python
def add_task(title: str, priority: int = 1) -> Task:
    \"\"\"Add task.\"\"\"
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
    pass
```

### DRY — extract shared logic

**DO:**
```python
def validate_task(title: str) -> None:
    if not title.strip():
        raise ValueError("Title cannot be empty")
```

**DON'T:**
```python
def add_task(title: str) -> Task:
    if not title.strip():
        raise ValueError("Title cannot be empty")
```

### File size — keep it small

| Scope | Max Lines |
|-------|-----------|
| Function | 50 |
| Class | 300 |
| File | 500 |

### Imports — top of file, grouped

**DO:**
```python
import json
import logging
from pathlib import Path
```

**DON'T:**
```python
from pydantic import *
import os, sys, json
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

### Naming conventions

Use snake_case for functions and variables.

**DO:**
```python
def process_thumbnail(input_path: Path) -> Path:
    max_retries = 3
```

**DON'T:**
```python
def ProcessThumbnail(inputPath):
    maxRetries = 3
```
"""


@pytest.fixture
def sample_claude_md_file(tmp_path: Path) -> Path:
    """Write the sample CLAUDE.md to a temp file."""
    md_file = tmp_path / "CLAUDE.md"
    md_file.write_text(SAMPLE_CLAUDE_MD, encoding="utf-8")
    return md_file


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseClaudeMdText:
    """Test in-memory markdown parsing via parse_claude_md_text."""

    def test_extracts_rules_from_sample(self) -> None:
        """Parser returns a non-empty list of rules from the sample file."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        assert len(rules) > 0

    def test_all_categories_valid(self) -> None:
        """Every extracted rule has a category from the allowed set."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        for rule in rules:
            assert rule.category in VALID_CATEGORIES, f"Invalid category: {rule.category}"

    def test_all_check_types_valid(self) -> None:
        """Every extracted rule has a valid check_type."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        for rule in rules:
            assert rule.check_type in VALID_CHECK_TYPES, f"Invalid check_type: {rule.check_type}"

    def test_type_hints_rule_extracted(self) -> None:
        """Parser recognises the type-hints section as a rule."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        type_hint_rules = [r for r in rules if r.category == "type_hints"]
        assert len(type_hint_rules) >= 1

    def test_type_hints_check_type_is_static(self) -> None:
        """Type-hint rules should be marked as static checks."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        type_hint_rules = [r for r in rules if r.category == "type_hints"]
        assert all(r.check_type == "static" for r in type_hint_rules)

    def test_error_handling_check_type_is_both(self) -> None:
        """Error-handling rules should be marked as 'both'."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        err_rules = [r for r in rules if r.category == "error_handling"]
        assert len(err_rules) >= 1
        assert all(r.check_type == "both" for r in err_rules)

    def test_file_size_rules_extracted_per_scope(self) -> None:
        """File-size table rows produce one rule per scope."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        size_rules = [r for r in rules if r.category == "file_size"]
        assert len(size_rules) == 3
        descriptions = {r.description for r in size_rules}
        assert "Function max 50 lines" in descriptions
        assert "Class max 300 lines" in descriptions
        assert "File max 500 lines" in descriptions

    def test_do_example_captured(self) -> None:
        """Rules with DO blocks capture the do_example text."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        type_hint_rules = [r for r in rules if r.category == "type_hints"]
        assert any(r.do_example != "" for r in type_hint_rules)

    def test_dont_example_captured(self) -> None:
        """Rules with DON'T blocks capture the dont_example text."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        type_hint_rules = [r for r in rules if r.category == "type_hints"]
        assert any(r.dont_example != "" for r in type_hint_rules)

    def test_unique_rule_ids(self) -> None:
        """All rule IDs must be unique."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        ids = [r.id for r in rules]
        assert len(ids) == len(set(ids))

    def test_imports_rule_extracted(self) -> None:
        """Parser recognises the imports section as a rule."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        import_rules = [r for r in rules if r.category == "imports"]
        assert len(import_rules) >= 1
        assert all(r.check_type == "static" for r in import_rules)

    def test_paths_rule_extracted(self) -> None:
        """Parser recognises the pathlib/paths section."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        path_rules = [r for r in rules if r.category == "paths"]
        assert len(path_rules) >= 1

    def test_dry_rule_extracted(self) -> None:
        """Parser recognises the DRY section."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        dry_rules = [r for r in rules if r.category == "dry"]
        assert len(dry_rules) >= 1
        assert all(r.check_type == "both" for r in dry_rules)

    def test_naming_rule_extracted(self) -> None:
        """Parser recognises the naming conventions section."""
        rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        naming_rules = [r for r in rules if r.category == "naming"]
        assert len(naming_rules) >= 1


class TestParseClaudeMdFile:
    """Test file-based parsing via parse_claude_md."""

    def test_parse_from_file(self, sample_claude_md_file: Path) -> None:
        """parse_claude_md reads a file and returns the same rules as the text variant."""
        file_rules = parse_claude_md(sample_claude_md_file)
        text_rules = parse_claude_md_text(SAMPLE_CLAUDE_MD)
        assert len(file_rules) == len(text_rules)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """parse_claude_md raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            parse_claude_md(tmp_path / "missing.md")


class TestEdgeCases:
    """Test edge cases: empty, no rules, minimal input."""

    def test_empty_string_returns_no_rules(self) -> None:
        """An empty string yields an empty list."""
        assert parse_claude_md_text("") == []

    def test_whitespace_only_returns_no_rules(self) -> None:
        """Whitespace-only content yields an empty list."""
        assert parse_claude_md_text("   \n\n  ") == []

    def test_no_sections_returns_no_rules(self) -> None:
        """Content without any ## headings yields an empty list."""
        assert parse_claude_md_text("# Title\nJust a paragraph.") == []

    def test_heading_without_rules_skipped(self) -> None:
        """Sections that don't match any rule pattern are skipped."""
        content = "## Random Section\n\nSome unrelated text."
        rules = parse_claude_md_text(content)
        assert len(rules) == 0

    def test_partial_rules_only_matching_extracted(self) -> None:
        """Only sections that match known patterns produce rules."""
        content = """\
## Project Overview

Just a description.

## Type hints — required

**DO:**
```python
def foo(x: int) -> int:
    ...
```
"""
        rules = parse_claude_md_text(content)
        assert len(rules) == 1
        assert rules[0].category == "type_hints"


class TestRuleDataclass:
    """Test the Rule dataclass itself."""

    def test_rule_is_frozen(self) -> None:
        """Rule instances should be immutable."""
        rule = Rule(id="test", category="general", description="test rule")
        with pytest.raises(AttributeError):
            rule.id = "changed"  # type: ignore[misc]

    def test_rule_default_values(self) -> None:
        """Rule defaults are applied correctly."""
        rule = Rule(id="test", category="general", description="test rule")
        assert rule.check_type == "static"
        assert rule.keywords == ()
        assert rule.source_section == ""
        assert rule.do_example == ""
        assert rule.dont_example == ""

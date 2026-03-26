# Unit Test Template

Use this template when writing pytest unit tests. Unit tests verify individual functions in isolation, mocking external dependencies.

## File Structure

```
<project_dir>/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # shared fixtures
│   ├── test_<module>.py     # one test file per source module
│   └── test_<module2>.py
```

## conftest.py — Shared Fixtures

```python
"""Shared fixtures for <project> tests."""

import json
from pathlib import Path

import pytest


SAMPLE_DATA: list[dict] = [
    {"id": 1, "name": "Item one", "active": True},
    {"id": 2, "name": "Item two", "active": False},
]


@pytest.fixture()
def data_store(tmp_path: Path) -> Path:
    """Create a temporary data file pre-populated with sample data.

    Returns:
        Path to the temporary JSON file.
    """
    store = tmp_path / "data.json"
    store.write_text(json.dumps(SAMPLE_DATA, indent=2) + "\n")
    return store


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for testing."""
    monkeypatch.setenv("API_KEY", "test-key-123")
    monkeypatch.setenv("ENV", "test")
```

## test_<module>.py — Test File

```python
"""Tests for the <feature> in <module> module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from <module> import <function_under_test>


class TestFunctionHappyPath:
    """Verify <function> works correctly with valid inputs."""

    def test_valid_input_returns_expected_result(self, data_store: Path) -> None:
        """Should return expected result with valid input."""
        result = function_under_test("valid input", store=data_store)

        assert result["id"] == 1
        assert result["name"] == "Valid"

    def test_returns_correct_type(self, data_store: Path) -> None:
        """Should return a dict with expected keys."""
        result = function_under_test("input", store=data_store)

        assert isinstance(result, dict)
        assert "id" in result


class TestFunctionEdgeCases:
    """Verify <function> handles edge cases correctly."""

    def test_empty_input_raises_value_error(self) -> None:
        """Should raise ValueError when input is empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            function_under_test("")

    def test_nonexistent_id_raises_key_error(self, data_store: Path) -> None:
        """Should raise KeyError when ID does not exist."""
        with pytest.raises(KeyError, match="not found"):
            function_under_test(999, store=data_store)

    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        """Should return empty list when store file does not exist."""
        missing = tmp_path / "nonexistent.json"
        result = function_under_test(store=missing)

        assert result == []


class TestFunctionWithMocks:
    """Verify <function> interacts correctly with external dependencies."""

    @patch("module.external_api_call")
    def test_calls_api_with_correct_args(self, mock_api: MagicMock) -> None:
        """Should call the external API with the expected arguments."""
        mock_api.return_value = {"status": "ok"}

        result = function_under_test("input")

        mock_api.assert_called_once_with("input")
        assert result["status"] == "ok"

    @patch("module.external_api_call")
    def test_api_failure_raises(self, mock_api: MagicMock) -> None:
        """Should propagate the error when the API call fails."""
        mock_api.side_effect = ConnectionError("timeout")

        with pytest.raises(ConnectionError, match="timeout"):
            function_under_test("input")


class TestFunctionParametrized:
    """Verify <function> with multiple input variations."""

    @pytest.mark.parametrize("input_val,expected", [
        ("a", 1),
        ("b", 2),
        ("c", 3),
    ])
    def test_returns_expected_for_each_input(
        self, input_val: str, expected: int
    ) -> None:
        """Should map each input to its expected output."""
        assert function_under_test(input_val) == expected
```

## Rules

| Rule | Detail |
|------|--------|
| One concern per test | Each test verifies exactly one behavior |
| Naming | `test_<scenario>_<expected_outcome>` |
| Class grouping | Group related tests by behavior: happy path, edge cases, mocks |
| Fixtures | `tmp_path` for files, `monkeypatch` for env vars, `conftest.py` for shared |
| Mocking | Mock at boundaries only (APIs, filesystem, subprocess, network) |
| Assertions | Specific values, not just truthiness. Use `pytest.raises(match=...)` |
| Parametrize | Same logic, different inputs → `@pytest.mark.parametrize` |
| Independence | No shared state, no order dependence, no globals |
| Test data | `tmp_path` or `test_content/`, NEVER real `content/` folders |
| Type hints | All test methods return `-> None`, parameters are typed |
| Docstrings | Every test method has a `"""Should ..."""` docstring |

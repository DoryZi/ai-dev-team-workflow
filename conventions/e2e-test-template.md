# End-to-End Test Template

Use this template when writing pytest e2e tests. E2E tests verify the full workflow from CLI input to final output — no mocks, real execution paths.

## File Structure

```
<project_dir>/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # shared fixtures (unit + e2e)
│   ├── test_<module>.py         # unit tests
│   └── test_<module>_e2e.py     # e2e tests (suffix: _e2e)
```

## conftest.py — E2E Fixtures

Add these alongside your unit test fixtures:

```python
import subprocess
from pathlib import Path

import pytest


@pytest.fixture()
def project_dir() -> Path:
    """Return the project root directory.

    Returns:
        Path to the directory containing pyproject.toml.
    """
    return Path(__file__).parent.parent


@pytest.fixture()
def cli_runner(project_dir: Path, tmp_path: Path):
    """Create a CLI runner that executes the app via uv run.

    Returns:
        A callable that runs CLI commands and returns CompletedProcess.
    """
    def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        """Run a CLI command via uv.

        Args:
            *args: Command arguments to pass after the script name.
            env: Optional environment variable overrides.

        Returns:
            CompletedProcess with stdout, stderr, and returncode.
        """
        import os
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        return subprocess.run(
            ["uv", "run", "--directory", str(project_dir), "python",
             "<script>.py", *args],
            capture_output=True,
            text=True,
            env=run_env,
            timeout=30,
        )

    return run
```

## test_<module>_e2e.py — E2E Test File

```python
"""End-to-end tests for the <project> CLI."""

import json
from pathlib import Path

import pytest


class TestCLIAddWorkflow:
    """Verify the full add workflow from CLI to persisted data."""

    def test_add_creates_item_and_prints_confirmation(
        self, cli_runner, tmp_path: Path
    ) -> None:
        """Should create an item in the store and print a confirmation."""
        store = tmp_path / "data.json"

        result = cli_runner("add", "Buy groceries", env={"STORE": str(store)})

        assert result.returncode == 0
        assert "Added" in result.stdout
        assert "Buy groceries" in result.stdout

        # Verify persistence
        data = json.loads(store.read_text())
        assert len(data) == 1
        assert data[0]["title"] == "Buy groceries"

    def test_add_empty_title_fails_with_error(self, cli_runner) -> None:
        """Should exit with error when title is empty."""
        result = cli_runner("add", "")

        assert result.returncode != 0


class TestCLIListWorkflow:
    """Verify the full list workflow including filtering."""

    def test_list_shows_active_items(
        self, cli_runner, tmp_path: Path
    ) -> None:
        """Should display only active items by default."""
        store = tmp_path / "data.json"
        store.write_text(json.dumps([
            {"id": 1, "title": "Active", "done": False},
            {"id": 2, "title": "Done", "done": True},
        ]))

        result = cli_runner("list", env={"STORE": str(store)})

        assert result.returncode == 0
        assert "Active" in result.stdout
        assert "Done" not in result.stdout

    def test_list_all_shows_completed(
        self, cli_runner, tmp_path: Path
    ) -> None:
        """Should display all items including completed with --all flag."""
        store = tmp_path / "data.json"
        store.write_text(json.dumps([
            {"id": 1, "title": "Active", "done": False},
            {"id": 2, "title": "Done", "done": True},
        ]))

        result = cli_runner("list", "--all", env={"STORE": str(store)})

        assert result.returncode == 0
        assert "Active" in result.stdout
        assert "Done" in result.stdout


class TestCLIRoundTrip:
    """Verify multi-step workflows that chain multiple commands."""

    def test_add_then_complete_then_list(
        self, cli_runner, tmp_path: Path
    ) -> None:
        """Should add an item, mark it done, and verify it's filtered."""
        store = tmp_path / "data.json"
        env = {"STORE": str(store)}

        # Add
        result = cli_runner("add", "Test task", env=env)
        assert result.returncode == 0

        # Complete
        result = cli_runner("done", "1", env=env)
        assert result.returncode == 0

        # List (default: active only)
        result = cli_runner("list", env=env)
        assert "Test task" not in result.stdout

        # List --all
        result = cli_runner("list", "--all", env=env)
        assert "Test task" in result.stdout


class TestCLIErrorHandling:
    """Verify CLI error output for invalid operations."""

    def test_invalid_command_shows_help(self, cli_runner) -> None:
        """Should show help text when no valid command is given."""
        result = cli_runner()

        # argparse may return 0 or 2 depending on config
        assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()

    def test_operation_on_missing_id_fails(
        self, cli_runner, tmp_path: Path
    ) -> None:
        """Should exit with non-zero when operating on a non-existent ID."""
        store = tmp_path / "data.json"
        store.write_text("[]")

        result = cli_runner("done", "999", env={"STORE": str(store)})

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
```

## Rules

| Rule | Detail |
|------|--------|
| Suffix | E2E test files end with `_e2e.py` to distinguish from unit tests |
| No mocks | E2E tests execute real code paths — no `@patch`, no `MagicMock` |
| CLI via subprocess | Run the CLI through `uv run` to test the real entry point |
| Isolated state | Each test uses `tmp_path` for data — no shared state between tests |
| Verify persistence | Check both CLI output AND the resulting files/database |
| Round-trip tests | Test multi-step workflows (add → complete → list) |
| Error paths | Test invalid inputs, missing resources, and bad arguments |
| Timeout | Set `timeout=30` on subprocess calls to prevent hangs |
| Environment | Pass config via env vars, never hardcoded paths |

## When to Use Unit vs E2E

| Aspect | Unit Test | E2E Test |
|--------|-----------|----------|
| Scope | Single function | Full CLI workflow |
| Mocks | Yes, at boundaries | No |
| Speed | Fast | Slower (subprocess) |
| What breaks | Logic bugs | Integration bugs, CLI parsing, persistence |
| Write first in TDD | Yes | After unit tests pass |

---
name: run-tests
description: Discover and run pytest tests in any project directory with pyproject.toml + tests/. Reports pass/fail with clean output. Takes an optional path argument to target a specific directory, or discovers all testable directories.
color: green
---

# Test Runner

Simple, mechanical test runner. Discover, execute, report. Never write or fix tests.

## Usage

```
/run-tests                                    # all testable directories
/run-tests task_tracker/                      # one specific directory
```

## Scope

**With argument:** target that single directory.
**Without argument:** discover all directories that contain both `pyproject.toml` and a `tests/` subdirectory. Use Glob to find `**/pyproject.toml`, then check each for `tests/`.

## Execution Order (per directory)

### 1. Check for test scripts

Look for `run_tests.sh`, `test.sh`, or `tests.sh` in the target directory.

**DO:**
```
# Found <dir>/run_tests.sh
# Show contents to user and ASK for permission before running
```

**DON'T:**
```bash
# Never auto-run test scripts
bash <dir>/run_tests.sh  # WRONG — need user approval first
```

If script found → show contents → ask user → run only if approved → report → next directory.
If user declines → fall through to pytest checks below.

### 2. Check for tests/ directory

No `tests/` dir → **SKIPPED (no tests)** → next directory.

### 3. Check for pyproject.toml

No `pyproject.toml` → **SKIPPED (no pyproject.toml)** → next directory.

### 4. Ensure pytest is available

```bash
uv run --directory <dir> python -m pytest --version 2>/dev/null
```

Not installed → install:
```bash
uv run --directory <dir> pip install pytest pytest-cov -q
```

### 5. Run pytest

```bash
uv run --directory <dir> python -m pytest <dir>/tests/ -v --tb=short 2>&1
```

Timeout: 120 seconds.

## Report Format

Per directory:
```
## <directory_name>
Status: PASSED | FAILED | SKIPPED (reason)
Tests: X passed, Y failed, Z errors
[short traceback if failed]
```

Final summary:
```
| Directory | Status | Passed | Failed |
|-----------|--------|--------|--------|
| dir_a | PASSED | 12 | 0 |
| dir_b | FAILED | 8 | 3 |
| dir_c | SKIPPED | - | - |

Total: X passed, Y failed, Z skipped
```

## Rules

**DO:**
- Use uv: `uv run --directory <dir> python -m pytest`
- Run pytest automatically (no permission needed)
- Ask user before running any `.sh` test scripts
- Report exactly what happened

**DON'T:**
- Modify any code (test or production)
- Use `source activate`, `venv/bin/python`, system Python, or bare `python3`
- Install packages other than `pytest` and `pytest-cov`
- Interpret results or suggest fixes
- Run `.sh` scripts without explicit user approval

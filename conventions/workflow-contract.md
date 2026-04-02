# Workflow Contract

The binding contract for how the TDD development pipeline operates. All agents, skills, and pipeline phases must follow these rules.

For Python coding rules, see `conventions/python-coding.md`.
For orchestration architecture and flow diagrams, see `conventions/orchestration-flow.md`.

---

## Acceptance Criteria Are the North Star

Everything in this workflow exists to satisfy the acceptance criteria. They are defined before any design or coding begins, and they determine whether the feature is done.

### What acceptance criteria are

Exact, testable conditions that define "done." Each criterion maps directly to one or more test assertions.

```
Good:
1. When upload_video() receives a file > 500MB, it raises FileTooLargeError
2. Retry logic attempts 3 times with exponential backoff before raising
3. Failed uploads log the error with structured context (file_path, attempt, elapsed_time)

Bad:
- "Upload works"
- "Error handling is implemented"
- "It should be fast"
```

### How everything traces back to ACs

| Artifact | Relationship to ACs |
|----------|---------------------|
| **Plan steps** | Every step must serve at least one AC. If it doesn't, it's unnecessary. |
| **Tests** | Each AC must have at least one test that verifies it. |
| **Implementation** | Code exists to make AC-derived tests pass. Nothing more. |
| **Final review** | Confirms every AC has passing tests. |
| **PR description** | Lists which ACs are satisfied and how. |

### Hard gate

No design, no coding, no test writing happens until acceptance criteria are defined and approved by the user. This is a pipeline blocker, not a suggestion.

---

## Agent Boundaries

| Agent | Role | Can Write | Cannot Write |
|-------|------|-----------|-------------|
| sys-arch | System architect (planning) | Nothing (read-only) | Everything |
| test-eng | Test engineer (execution) | Test files only | Production code |
| sde | Software engineer (execution) | Production code only | Test files |

### Boundary flexibility based on task size

- **Large tasks** — sys-arch provides high-level direction (e.g., "Add an authentication layer with token refresh"). SDE has design freedom to decide file structure, function signatures, and implementation details during execution.
- **Small/focused tasks** — sys-arch can specify exact files, function signatures, and module structure. SDE follows the plan closely.

The key invariant: **test-eng never touches production code, SDE never touches test files.** This boundary is always strict regardless of task size.

---

## TDD Phase Rules

### RED — Tests Must Fail

- test-eng writes tests for the current step based on the plan and acceptance criteria
- Tests MUST fail when first run (production code doesn't exist yet)
- Failures must be for the right reason (missing behavior, not import/syntax errors)
- Test files are committed at this point

### GREEN — Minimal Code to Pass

- SDE reads the failing tests — they are the spec
- SDE implements the minimum production code to make tests pass
- SDE does NOT write or modify any test files
- When plan steps are high-level, SDE decides file structure and design

### VERIFY — All Tests Pass

- Run ALL tests for steps 1..N (not just the current step)
- If tests fail, SDE fixes production code and re-runs (max 3 attempts)
- If still failing after 3 attempts, report to user and stop

### LINT — Code Formatting and Static Checks

- Run `ruff format` and `ruff check` on changed files
- Auto-fix where possible, report remaining violations
- Max 3 attempts to resolve lint issues

### COMMIT — Save Progress

- Commit the step's changes with a descriptive message
- Conventional commit style: `Add tests for <feature>` (RED), `Implement <feature>` (GREEN)

### FINAL REVIEW — Quality Gate

- Runs once after all steps complete
- Mechanical static checks (file size, print calls, secrets, function length)
- `/review` on the full branch diff
- This is the gate before PR creation

---

## Test Conventions

### Framework

- **pytest** — always. Never unittest.TestCase or Django TestCase.
- Fixtures in `conftest.py`, `tmp_path` for temporary files
- `pytest.raises` for exception testing
- `@pytest.mark.parametrize` for input variants

### File locations

| Test type | Location | When to use |
|-----------|----------|-------------|
| Unit tests | `<project>/tests/test_<module>.py` | Pure logic, functions, classes |
| E2E tests | `<project>/tests/test_<module>_e2e.py` | CLI tools, subprocess-based flows |

### Naming

- Method: `test_<what>_<condition>_<expected>`
- Class: `Test<Feature>`
- Example: `test_retry_when_timeout_returns_success`

### Test quality

- One concern per test
- Both positive AND negative tests for every feature
- Arrange / Act / Assert structure
- Mock at boundaries only (filesystem, APIs, subprocess, network)
- No shared state between tests, no order dependence
- Test data in `test_content/` or `tmp_path`, NEVER real `content/` folders

### Tests must map to acceptance criteria

When test-eng writes tests for a step:
1. Check which acceptance criteria the step addresses
2. Write at least one test per AC that the step covers
3. Include both positive tests (AC is satisfied) and negative tests (AC rejects invalid input)

When all steps are complete, every AC must have at least one passing test.

---

## Commit Conventions

- Do NOT include `Co-Authored-By` in commit messages
- Commit test files separately before implementation (RED commit, then GREEN commit)
- Use conventional commit style: `Add tests for <feature>`, `Implement <feature>`
- Commit after each step passes verification

---

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Feature branch | `<user>/tdd-<slug>` | `dory/tdd-upload-retry` |
| Unit test file | `<project>/tests/test_<module>.py` | `agent_tools/buffer_api/tests/test_schedule.py` |
| Test class | `Test<Feature>` | `TestUploadRetry` |
| Test method | `test_<what>_<condition>_<expected>` | `test_retry_when_timeout_returns_success` |
| E2E test file | `<project>/tests/test_<module>_e2e.py` | `agent_tools/buffer_api/tests/test_schedule_e2e.py` |
| Plan file | `plans/<slug>-YYYY-MM-DD.md` | `plans/upload-retry-2026-04-01.md` |

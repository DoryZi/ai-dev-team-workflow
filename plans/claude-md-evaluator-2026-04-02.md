# CLAUDE.md Evaluator

## Acceptance Criteria

- [ ] AC1: CLI accepts one or more CLAUDE.md file paths and a problem set selection, runs evaluation end-to-end
- [ ] AC2: Ships with at least 3 built-in coding problems, each with a prompt, reference solution, and test cases
- [ ] AC3: For each problem, invokes `claude -p` in an isolated temp directory with the CLAUDE.md present, captures generated code
- [ ] AC4: Runs static analysis (ruff + AST checks) on generated code and scores rule adherence based on rules parsed from the CLAUDE.md
- [ ] AC5: Runs test cases against generated code via subprocess with configurable timeout, captures pass/fail and timing
- [ ] AC6: Runs LLM-as-judge evaluation against a configurable rubric (YAML file with dimensions and weights)
- [ ] AC7: Produces a structured JSON report per CLAUDE.md with per-problem scores, timing, and aggregate totals
- [ ] AC8: Renders each JSON report as a self-contained HTML page (embedded CSS/JS, no external dependencies)
- [ ] AC9: Users can add custom coding problems by adding a folder with prompt, tests, and optional reference solution
- [ ] AC10: All runs are isolated — temp directories, subprocess timeouts, cleanup after each run

## Step 1 — Project scaffolding

Set up `claude_md_evaluator/` with `pyproject.toml`, package structure, and CLI entry point.

Files:
- `claude_md_evaluator/pyproject.toml`
- `claude_md_evaluator/evaluator/__init__.py`
- `claude_md_evaluator/evaluator/cli.py`

Test classification: unit

- AC: AC1

## Step 2 — Built-in problem bank

Create the problem bank structure and 3 built-in problems. Each problem is a folder with `prompt.md`, `tests/test_solution.py`, and optional `reference_solution.py`.

Problems:
1. **LRU Cache** — implement an LRU cache class with get/put operations
2. **CSV Parser** — parse CSV with error handling, type coercion, and validation
3. **Task Manager** — CRUD operations on tasks with persistence to JSON file

Files:
- `claude_md_evaluator/problems/lru_cache/prompt.md`
- `claude_md_evaluator/problems/lru_cache/tests/test_solution.py`
- `claude_md_evaluator/problems/lru_cache/reference_solution.py`
- `claude_md_evaluator/problems/csv_parser/prompt.md`
- `claude_md_evaluator/problems/csv_parser/tests/test_solution.py`
- `claude_md_evaluator/problems/csv_parser/reference_solution.py`
- `claude_md_evaluator/problems/task_manager/prompt.md`
- `claude_md_evaluator/problems/task_manager/tests/test_solution.py`
- `claude_md_evaluator/problems/task_manager/reference_solution.py`
- `claude_md_evaluator/evaluator/problems.py` (discovery + loading)

Test classification: unit

- AC: AC2, AC9

## Step 3 — CLAUDE.md rule parser

Parse a CLAUDE.md file and extract actionable rules (type hints required, use pathlib, docstrings on public functions, etc.). Output a structured list of rules with categories.

Files:
- `claude_md_evaluator/evaluator/rule_parser.py`

Test classification: unit

- AC: AC4

## Step 4 — Code generation runner

Invoke `claude -p` in an isolated temp directory with the CLAUDE.md copied in. Capture the generated code output, extract Python code blocks, write to file.

Files:
- `claude_md_evaluator/evaluator/runner.py`

Test classification: unit + e2e

- AC: AC3, AC10

## Step 5 — Static analysis scorer

Run ruff + AST-based checks on generated code. Score against rules extracted in Step 3 (e.g., check for type hints, docstrings, pathlib usage, import ordering).

Files:
- `claude_md_evaluator/evaluator/static_analysis.py`

Test classification: unit

- AC: AC4

## Step 6 — Test case runner

Execute the problem's test suite against the generated code via subprocess with configurable timeout. Capture pass/fail per test, stdout/stderr, and wall-clock timing.

Files:
- `claude_md_evaluator/evaluator/test_runner.py`

Test classification: unit + e2e

- AC: AC5, AC10

## Step 7 — LLM-as-judge evaluator

Load a configurable rubric (YAML with dimensions like readability, error handling, efficiency + weights). Send generated code + rubric to Claude API for scoring. Parse structured response.

Files:
- `claude_md_evaluator/evaluator/llm_judge.py`
- `claude_md_evaluator/rubrics/default.yaml`

Test classification: unit

- AC: AC6

## Step 8 — Report aggregator (JSON)

Collect results from static analysis, test runner, and LLM judge. Aggregate into a structured JSON report per CLAUDE.md with per-problem breakdowns and overall scores.

Files:
- `claude_md_evaluator/evaluator/report.py`

Test classification: unit

- AC: AC7

## Step 9 — HTML report renderer

Take JSON report and render a self-contained HTML page. Embedded CSS for styling (clean, modern look), embedded JS for interactivity (expand/collapse per problem, score highlighting).

Files:
- `claude_md_evaluator/evaluator/html_renderer.py`
- `claude_md_evaluator/evaluator/templates/report.html` (Jinja2 template)

Test classification: unit

- AC: AC8

## Step 10 — CLI wiring and end-to-end flow

Wire all components together in the CLI. Handle argument parsing, progress output, error handling. Run full end-to-end flow.

Files:
- `claude_md_evaluator/evaluator/cli.py` (update)
- `claude_md_evaluator/evaluator/orchestrator.py`

Test classification: e2e

- AC: AC1, AC7

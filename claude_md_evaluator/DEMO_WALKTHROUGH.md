# CLAUDE.md Evaluator — Build Demo Walkthrough

> A complete multi-agent development session: from idea to working tool in one conversation.

---

## Phase 1: Planning (`/plan`)

### Stage 1 — Understanding

The user described the goal:

> "I need to build an evaluator that can take a CLAUDE.md file, run it through a few coding tasks and measure the output against rule adherence, how good is the code, how performant."

**8 clarifying questions** were asked covering:
- Execution method (Claude CLI vs API)
- Task source (predefined problems vs generated)
- Project location (standalone directory)
- Evaluation dimensions (static + LLM-as-judge)
- Quality rubric (configurable YAML)
- Performance (wall-clock timing)
- Output format (JSON + HTML)
- Audience (open-source demo tool)

### Stage 2 — Design Decisions

Key decisions made through back-and-forth:

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Code generation | `claude -p` CLI | Simulates real CLAUDE.md experience |
| Coding problems | Known problems with solutions | Reproducible, testable |
| Sandboxing | Temp dirs + subprocess timeout | Simple for demo, no Docker dependency |
| Multi-file support | Independent reports per CLAUDE.md | Simple loop, compare side-by-side |
| Correctness | Run generated code against test cases | Real validation, not just LLM comparison |

### Stage 3 — Acceptance Criteria

10 acceptance criteria were drafted and approved:

- [ ] AC1: CLI accepts CLAUDE.md files + problem selection, runs end-to-end
- [ ] AC2: 3 built-in coding problems with prompts, solutions, and tests
- [ ] AC3: Invokes `claude -p` in isolated temp directories
- [ ] AC4: Static analysis (ruff + AST) scores rule adherence from parsed CLAUDE.md
- [ ] AC5: Runs test cases with configurable timeout, captures pass/fail + timing
- [ ] AC6: LLM-as-judge with configurable rubric (YAML)
- [ ] AC7: Structured JSON report per CLAUDE.md
- [ ] AC8: Self-contained HTML report (embedded CSS/JS)
- [ ] AC9: Custom problems via folder with prompt + tests
- [ ] AC10: All runs isolated — temp dirs, timeouts, cleanup

### Stage 4 — Implementation Plan

10 steps designed with dependency analysis for maximum parallelism:

```
Step 1:  Project scaffolding           ─┐
Step 2:  Built-in problem bank         ─┤── Foundation (sequential)
Step 3:  CLAUDE.md rule parser         ─┘
                                        │
Step 4:  Code generation runner        ─┐
Step 5:  Static analysis scorer        ─┤── Core engine (parallel)
Step 6:  Test case runner              ─┤
Step 7:  LLM-as-judge evaluator        ─┘
                                        │
Step 8:  Report aggregator (JSON)      ─┐
Step 9:  HTML report renderer          ─┤── Output layer (parallel)
Step 10: CLI wiring + orchestrator     ─┘
```

Plan saved to `plans/claude-md-evaluator-2026-04-02.md`.

---

## Phase 2: Execution (`/dev-cycle`)

### Pipeline Bootstrapping

First attempt used the automated TDD pipeline (`agent_tools/dev_cycle/run.py`), which hit an import error:

```
ImportError: cannot import name 'Agent' from 'claude_agent_sdk'
```

The `claude_agent_sdk` API had changed — `Agent`/`run_agent` were replaced by `query()`/`ClaudeAgentOptions`. **Fixed the tool** (as per project rules: "if a tool fails, fix the tool"), then switched to direct agent orchestration for the remaining steps.

### Step 1 — Project Scaffolding

**Agent:** TDD pipeline (RED → GREEN → VERIFY)
**Duration:** ~9 minutes
**Cost:** $2.23
**Result:** 36 tests passing

Created:
- `pyproject.toml` with all dependencies (click, pytest, ruff, pyyaml, jinja2, anthropic)
- `evaluator/__init__.py` with version
- `evaluator/cli.py` with full argparse CLI
- `tests/test_cli.py` (22 tests) + `tests/test_package_structure.py` (14 tests)

### Steps 2 + 3 — Parallel (Problem Bank + Rule Parser)

**Agents:** 2 SDE agents in parallel
**Duration:** ~4 minutes (wall clock)

**Step 2 — Problem Bank:**
- 3 problems: LRU Cache (17 tests), CSV Parser (17 tests), Task Manager (16 tests)
- Each with `prompt.md`, `reference_solution.py`, `tests/test_solution.py`
- `evaluator/problems.py` with discovery + loading
- All 50 reference solution tests pass

**Step 3 — Rule Parser:**
- `evaluator/rule_parser.py` — pattern-based extraction from any CLAUDE.md
- Handles: type hints, docstrings, imports, paths, error handling, naming, file size, DRY
- 23 new tests, all 59 total pass

### Steps 4 + 5 + 6 + 7 — Parallel (Core Engine)

**Agents:** 4 SDE agents in parallel
**Duration:** ~7 minutes (wall clock)

**Step 4 — Code Generation Runner:**
- `evaluator/runner.py` — invokes `claude -p` in temp dirs
- Extracts Python code blocks from markdown output
- Handles timeout, missing CLI, no code found

**Step 5 — Static Analysis Scorer:**
- `evaluator/checkers.py` — 6 AST-based checkers (type hints, docstrings, imports, paths, error handling, file size)
- `evaluator/static_analysis.py` — orchestrator + ruff integration
- `evaluator/models.py` — shared dataclasses

**Step 6 — Test Case Runner:**
- `evaluator/test_runner.py` — copies tests into solution dir, runs pytest
- Parses JUnit XML for structured per-test results
- Handles timeout, import errors, syntax errors

**Step 7 — LLM-as-Judge:**
- `evaluator/llm_judge.py` — Anthropic API with structured JSON output
- `rubrics/default.yaml` — 5 dimensions (readability, error handling, efficiency, correctness, best practices)
- Graceful degradation when API key missing

### Steps 8 + 9 + 10 — Parallel (Output + Wiring)

**Agents:** 3 SDE agents in parallel
**Duration:** ~4 minutes (wall clock)

**Step 8 — Report Aggregator:**
- `evaluator/report.py` — builds JSON reports with weighted scoring
- Weights: tests 40%, static analysis 25%, LLM judge 25%, generation 10%
- Save/load round-trip support

**Step 9 — HTML Renderer:**
- `evaluator/html_renderer.py` + `templates/report.html`
- Self-contained (all CSS/JS inline), dark/light mode
- Collapsible sections, color-coded scores, responsive layout
- 11 tests

**Step 10 — Orchestrator + CLI:**
- `evaluator/orchestrator.py` — async pipeline wiring all phases
- Updated `cli.py` with `--timeout` and `--rubric` flags
- Graceful error handling per-problem

---

## Final Results

### Test Suite

```
70 passed in 64.84s
```

### Project Structure

```
claude_md_evaluator/
├── pyproject.toml
├── rubrics/
│   └── default.yaml              # Configurable quality rubric
├── problems/                      # Built-in coding problems
│   ├── lru_cache/
│   │   ├── prompt.md
│   │   ├── reference_solution.py
│   │   └── tests/test_solution.py
│   ├── csv_parser/
│   │   ├── prompt.md
│   │   ├── reference_solution.py
│   │   └── tests/test_solution.py
│   └── task_manager/
│       ├── prompt.md
│       ├── reference_solution.py
│       └── tests/test_solution.py
├── evaluator/
│   ├── __init__.py
│   ├── cli.py                     # CLI entry point
│   ├── orchestrator.py            # Pipeline orchestration
│   ├── problems.py                # Problem discovery + loading
│   ├── rule_parser.py             # CLAUDE.md → rules
│   ├── runner.py                  # claude -p invocation
│   ├── checkers.py                # AST-based code checks
│   ├── static_analysis.py         # Static analysis orchestrator
│   ├── models.py                  # Shared dataclasses
│   ├── test_runner.py             # Pytest execution
│   ├── llm_judge.py               # LLM-as-judge evaluation
│   ├── report.py                  # JSON report builder
│   ├── html_renderer.py           # HTML report renderer
│   └── templates/
│       └── report.html            # Jinja2 template
└── tests/
    ├── conftest.py
    ├── test_cli.py
    ├── test_html_renderer.py
    ├── test_package_structure.py
    └── test_rule_parser.py
```

### Usage

```bash
# Evaluate a single CLAUDE.md
uv run --directory claude_md_evaluator claude-md-eval path/to/CLAUDE.md

# Evaluate multiple files, specific problems
uv run --directory claude_md_evaluator claude-md-eval a.md b.md --problems lru_cache,csv_parser

# Custom rubric and timeout
uv run --directory claude_md_evaluator claude-md-eval CLAUDE.md --rubric my_rubric.yaml --timeout 180

# Output to specific directory
uv run --directory claude_md_evaluator claude-md-eval CLAUDE.md --output-dir ./results
```

### Evaluation Pipeline

```
CLAUDE.md ──→ Parse Rules
                  │
Problem Bank ──→ For each problem:
                  │
                  ├─→ claude -p (generate solution)
                  │       │
                  ├─→ Static Analysis (ruff + AST vs parsed rules)
                  │       │
                  ├─→ Run Tests (pytest against problem test suite)
                  │       │
                  └─→ LLM Judge (Anthropic API + rubric)
                          │
                          ▼
                  JSON Report ──→ HTML Report
```

---

## Execution Stats

| Metric | Value |
|--------|-------|
| Total steps | 10 |
| Parallel batches | 4 (steps 2-3, 4-7, 8-10, plus step 1 solo) |
| Total agents spawned | 10 (1 pipeline + 9 SDE agents) |
| Max concurrent agents | 4 |
| Tests written | 70 |
| Problem test cases | 50 |
| Source files | 15 (.py) + 1 (.html) + 1 (.yaml) + 3 (.md prompts) |
| Pipeline fix | `claude_agent_sdk` import migration (Agent → query) |

---

## Key Takeaways

1. **Planning before coding** — The `/plan` skill forced alignment on scope, design decisions, and acceptance criteria before any code was written.

2. **Parallel agent execution** — Steps with no dependencies ran concurrently (4 agents at once), dramatically reducing wall-clock time.

3. **Fix the tool, not the workflow** — When the TDD pipeline broke due to an SDK API change, the tool was fixed rather than working around it.

4. **Test-first foundation** — Step 1 established 36 tests for the scaffolding. Every subsequent step maintained the green test suite (never dropped below 59 passing).

5. **Incremental verification** — After each parallel batch completed, a full test run confirmed no regressions before launching the next batch.

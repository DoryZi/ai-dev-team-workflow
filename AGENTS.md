# AGENTS.md — AI Dev Team Workflow

Multi-agent Python development with Claude Code. Three skills cover the loop: `/plan` designs a change, `/dev-cycle` builds it, `/verify` proves it meets the plan.

## Agents

### sys-arch (Systems Architect)

- **Role**: Researches the codebase and designs plans for `/plan`
- **Never touches**: Any file. Read-only
- **Definition**: `.claude/agents/sys-arch.md`

### sde (Staff Software Engineer)

- **Role**: Writes and modifies production code only, thinks like a staff engineer
- **Never touches**: Test files. That boundary is absolute
- **Smoke test**: Runs the code end-to-end after every change to verify it works
- **Standards**: Enforces `conventions/python-coding.md`: type hints, docstrings, pathlib, structured logging, size limits
- **Execution**: Always uses `uv run --directory`, never venv, system Python, or bare `python3`
- **Definition**: `.claude/agents/sde.md`

### test-eng (Test Engineer)

- **Role**: Writes unit and e2e tests against acceptance criteria
- **Never touches**: Production code. Reports bugs instead
- **Standards**: One concern per test, `tmp_path` for files, mocks only at boundaries, `pytest.raises` for exceptions
- **Execution**: Uses `/run-tests` for all test runs
- **Definition**: `.claude/agents/test-eng.md`

### verifier (Verification Engineer)

- **Role**: Proves a change meets the plan's acceptance criteria. Writes and runs checks in its own context, reports PASS or FAIL per criterion with command output
- **Never touches**: Production code. Code bugs are findings, not fixes
- **Drivers**: `claude` (default), `codex`, or `cursor`. With an external driver, the verdict still comes from commands the verifier re-ran itself
- **Definition**: `.claude/agents/verifier.md`

### Pipeline agents

`/dev-cycle` runs its own headless agents (explore, implement, review, eng-review) through the Claude Agent SDK. Their prompts live in `agent_tools/dev_cycle/prompts/`.

## Skills (Slash Commands)

| Skill | What it does |
|-------|--------------|
| `/plan` | Interactive: understand → explore → acceptance criteria → verification table → steps. Saves `plans/<slug>-YYYY-MM-DD.md` and `.html` |
| `/dev-cycle` | Automated: EXPLORE, then IMPLEMENT → VERIFY → REVIEW → COMMIT per step, then final review |
| `/verify` | Runs the plan's verification table in a separate agent, PASS or FAIL per criterion |
| `/run-tests` | Discovers and runs pytest across project directories |
| `/python-reviewer` | Static analysis (ruff, mypy, black) + AI code review → DO/DON'T report |
| `/review` | AI code review on working tree diff |
| `/dev-tdd`, `/dev-fast` | v1 orchestrators. Deprecated, kept for reference |

## Orchestration Pattern

```
User request
    │
    ▼
/plan (user approves each stage)
    │   plans/<slug>-YYYY-MM-DD.md (acceptance criteria + verification table)
    ▼
/dev-cycle (headless pipeline: agent_tools/dev_cycle)
    │
    ├── EXPLORE: research the codebase once (skip with --no-explore)
    ├── per step: IMPLEMENT → VERIFY (lint + full pytest) → REVIEW (by --review-mode) → COMMIT
    └── FINAL REVIEW
    │
    ▼
/verify (verifier agent, fresh context)
    └── PASS or FAIL per acceptance criterion, with evidence
```

## Key Boundaries

- **Planning is interactive, execution is headless.** `/plan` waits for the user; `/dev-cycle` runs on its own
- **The orchestrator controls the flow, not the LLM.** Phase order and retries live in `agent_tools/dev_cycle/state_machine.py`
- **Acceptance criteria are the spec.** Every criterion maps to a verification row, and `/verify` checks every row
- **Checkers don't fix.** test-eng and verifier report production bugs instead of editing production code
- **All execution** goes through `uv run --directory`, no exceptions

## Conventions

- Agent definitions: `.claude/agents/<name>.md`
- Skill definitions: `.claude/skills/<name>/SKILL.md`
- Coding standards: `conventions/python-coding.md`
- Phase rules and agent boundaries: `conventions/workflow-contract.md`
- Pipeline architecture: `conventions/orchestration-flow.md`
- Agent and skill templates: `conventions/agent-template.md`, `conventions/skill-template.md`
- Test templates: `conventions/unit-test-template.md`, `conventions/e2e-test-template.md`

## Adapting for Your Project

1. Replace `task_tracker/` with your own Python project (needs `pyproject.toml`)
2. Edit `CLAUDE.md` with your project-specific rules
3. Edit `conventions/python-coding.md` to match your style
4. Create new agents in `.claude/agents/` using `conventions/agent-template.md`
5. Create new skills in `.claude/skills/` using `conventions/skill-template.md`

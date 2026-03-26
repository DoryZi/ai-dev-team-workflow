# AGENTS.md — AI Dev Team Workflow

Multi-agent Python development with Claude Code. Specialized agents collaborate through slash commands to plan, code, test, and review — like a real engineering team.

## Agents

### sde (Software Development Engineer)

- **Role**: Writes and modifies production code only
- **Never touches**: Test files
- **Standards**: Enforces `conventions/python-coding.md` — type hints, docstrings, pathlib, structured logging, size limits
- **Execution**: Always uses `uv run --directory` — never venv, system Python, or bare `python3`
- **Definition**: `.claude/agents/sde.md`

### test-eng (Test Engineer)

- **Role**: Writes and fixes test code only
- **Never touches**: Production code — reports bugs to the user instead
- **Standards**: One concern per test, `tmp_path` for files, mocks only at boundaries, `pytest.raises` for exceptions
- **Execution**: Uses `/run-tests` skill for all test execution
- **Definition**: `.claude/agents/test-eng.md`

## Skills (Slash Commands)

| Skill | What it orchestrates |
|-------|---------------------|
| `/dev-tdd` | Full TDD cycle: plan → tests first → code → test loop → review → verify |
| `/dev-fast` | Code-first cycle: plan → code → tests → test loop → review → verify |
| `/run-tests` | Discovers and runs pytest across project directories |
| `/python-reviewer` | Static analysis (ruff, mypy, black) + AI code review → DO/DON'T report |
| `/review` | AI code review on working tree diff |

## Orchestration Pattern

```
User request
    │
    ▼
/dev-tdd or /dev-fast (orchestrator)
    │
    ├── Phase 1: sde agent → plan (user approves)
    ├── Phase 2: test-eng or sde → write tests or code first
    ├── Phase 3: /run-tests → verify
    ├── Phase 4: sde agent → self-healing loop (fix → test → repeat, max 3)
    ├── Phase 5: /python-reviewer → review loop (fix → test → review, max 3)
    └── Phase 6: /run-tests → final verification
```

## Key Boundaries

- **sde** writes production code, **test-eng** writes tests — never crossed
- **Orchestrator skills** (`/dev-tdd`, `/dev-fast`) coordinate agents — agents don't call each other
- **All execution** goes through `uv run --directory` — no exceptions
- **All test runs** go through `/run-tests` — agents don't run pytest directly
- **All reviews** go through `/python-reviewer` — agents don't review their own code

## Conventions

- Agent definitions: `.claude/agents/<name>.md`
- Skill definitions: `.claude/skills/<name>/SKILL.md`
- Coding standards: `conventions/python-coding.md`
- Agent and skill templates: `conventions/agent-template.md`, `conventions/skill-template.md`

## Adapting for Your Project

1. Replace `task_tracker/` with your own Python project (needs `pyproject.toml`)
2. Edit `CLAUDE.md` with your project-specific rules
3. Edit `conventions/python-coding.md` to match your style
4. Create new agents in `.claude/agents/` using `conventions/agent-template.md`
5. Create new skills in `.claude/skills/` using `conventions/skill-template.md`

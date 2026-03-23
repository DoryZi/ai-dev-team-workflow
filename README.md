# AI Dev Team Workflow

Multi-agent Python development with [Claude Code](https://claude.ai/claude-code). Specialized AI agents collaborate through slash commands to plan, code, test, and review — like a real engineering team.

## Quick Start

```bash
# Clone with submodule
git clone --recurse-submodules https://github.com/DoryZi/ai-dev-team-workflow.git
cd ai-dev-team-workflow

# Open in Claude Code and run the demo
/dev-tdd task_tracker "Add delete task feature"
```

This triggers the full TDD cycle and you can watch the agents work:

1. **sde** plans the implementation
2. **test-eng** writes tests for the delete feature (red phase — tests fail)
3. **sde** writes code to make them pass (green phase)
4. **/run-tests** verifies everything passes
5. **/python-reviewer** reviews the final code

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  /dev-tdd                        │
│              (orchestrator skill)                │
├────────┬──────────┬──────────────┬──────────────┤
│  Plan  │  Tests   │    Code      │   Review     │
│        │          │              │              │
│  sde   │ test-eng │    sde       │ code-reviewer│
│ agent  │  agent   │   agent      │    agent     │
├────────┴──────────┴──────────────┴──────────────┤
│              /run-tests                          │
│         (discovers & runs pytest)                │
└─────────────────────────────────────────────────┘
```

## Agents

| Agent | Role | Writes |
|-------|------|--------|
| **sde** | Python developer | Production code only |
| **test-eng** | Test engineer | Test code only |

Agents are defined in `.claude/agents/` and enforce strict boundaries: sde never touches tests, test-eng never touches production code.

## Skills (Slash Commands)

| Skill | Description |
|-------|-------------|
| `/dev-tdd` | Full TDD: plan → tests first → code → test loop → review |
| `/dev-fast` | Code-first: plan → code → tests → test loop → review |
| `/run-tests` | Discover and run pytest across all project directories |
| `/python-reviewer` | Static analysis + code review on changes |
| `/review` | AI code review on working tree diff |

## Project Structure

```
ai-dev-team-workflow/
├── task_tracker/              ← sample app (the code being developed)
│   ├── pyproject.toml
│   ├── tracker.py
│   └── tests/
├── .claude/
│   ├── agents/                ← agent definitions
│   │   ├── sde.md
│   │   └── test-eng.md
│   └── skills/                ← slash command definitions
│       ├── dev-tdd/
│       ├── dev-fast/
│       ├── run-tests/
│       ├── python-reviewer/
│       └── review/
├── conventions/
│   └── python-coding.md       ← coding standards (agents reference this)
├── ai-code-review-demo/       ← git submodule (provides /review skill)
├── CLAUDE.md                  ← project rules & code boundaries
├── sync-from-source.sh        ← sync agents/skills from source repo
└── README.md
```

## Demo Scenario

The `task_tracker/` app is a simple CLI task manager that supports add, list, and complete. The **delete feature is intentionally missing** — that's the task you give to `/dev-tdd` to demonstrate the full multi-agent workflow.

### Available commands

| Command | What it does |
|---------|-------------|
| `/dev-tdd task_tracker "Add delete task feature"` | TDD workflow (tests first) |
| `/dev-fast task_tracker "Add task priority support"` | Code-first workflow |
| `/run-tests task_tracker` | Run tests for task_tracker |
| `/python-reviewer` | Review uncommitted changes |
| `/review` | AI code review on diff |

## Adapting for Your Project

1. Replace `task_tracker/` with your own Python project (needs `pyproject.toml`)
2. Adjust `CLAUDE.md` with your project-specific rules and boundaries
3. Optionally edit `conventions/python-coding.md` to match your style

The agents and skills work with any uv-managed Python project directory.

## Syncing from Source

This repo's agents, skills, and conventions are synced from [ai_will_replace_you](https://github.com/DoryZi/ai_will_replace_you). To pull updates:

```bash
./sync-from-source.sh            # copy latest files
./sync-from-source.sh --dry-run  # preview what would change
```

## License

MIT

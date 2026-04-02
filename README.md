# AI Dev Team Workflow

Multi-agent Python development with [Claude Code](https://claude.ai/claude-code). Specialized AI agents collaborate through slash commands to plan, code, test, and review — like a real engineering team.

## What's New (v2 — TDD Pipeline)

This version replaces the original `/dev-tdd` and `/dev-fast` skills with a two-skill architecture:

- **`/plan`** — interactive research and design (user in the loop)
- **`/dev-cycle`** — automated TDD execution pipeline (headless)

### Why the rewrite?

v1 relied on a single Claude Code session orchestrating everything inline — one prompt juggling planning, test writing, implementation, and review. It worked, but it was brittle and non-deterministic: steps got skipped, agent roles blurred, and there was no way to retry a failed phase or resume from where you left off.

v2 fixes this by separating **planning** (interactive, human-in-the-loop) from **execution** (programmatic, headless). The execution pipeline (`/dev-cycle`) is a Python program with a proper state machine and retry policies. It uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) to spawn isolated sub-agents (sde, test-eng) with strict role boundaries — each agent gets its own context, tools, and instructions. The orchestrator controls the flow, not the LLM.

> Looking for the original v1 agents? See [`README-v1-tdd-agents.md`](README-v1-tdd-agents.md) or check out the [`v1-before-refactor`](../../tree/v1-before-refactor) tag.

## Quick Start

```bash
# Clone with submodule
git clone --recurse-submodules https://github.com/DoryZi/ai-dev-team-workflow.git
cd ai-dev-team-workflow

# 1. Plan the feature (interactive)
/plan "Add delete task feature to task_tracker"

# 2. Execute the plan (automated TDD pipeline)
/dev-cycle plans/<your-plan>.md
```

## Architecture

```
/plan (interactive)              /dev-cycle (automated)
┌─────────────────────┐         ┌─────────────────────────┐
│ Research & Design    │         │ Execution               │
│                     │         │                         │
│ • Understand task   │         │ For each step:          │
│ • Explore codebase  │  plan   │  • RED   — test-eng     │
│ • Define ACs        │ ─────→  │  • GREEN — sde          │
│ • Design steps      │  .md    │  • VERIFY — pytest      │
│ • Save plan         │  file   │  • LINT  — ruff         │
│                     │         │  • COMMIT               │
│ User in the loop    │         │                         │
│ at every stage      │         │ Then: FINAL REVIEW      │
└─────────────────────┘         │  static checks + /review│
                                └─────────────────────────┘
```

See [`conventions/orchestration-flow.md`](conventions/orchestration-flow.md) for the full state machine diagrams and phase transitions.

## Agents

| Agent | Role | Used by |
|-------|------|---------|
| **sys-arch** | Systems architect — researches codebase, designs plans (read-only) | `/plan` |
| **sde** | Staff software engineer — writes production code, runs smoke tests | `/dev-cycle` |
| **test-eng** | Senior test engineer — writes unit + e2e tests against acceptance criteria | `/dev-cycle` |

Agents are defined in `.claude/agents/` and enforce strict boundaries: sde never touches tests, test-eng never touches production code, sys-arch never writes files.

## Skills (Slash Commands)

| Skill | Description |
|-------|-------------|
| `/plan` | Interactive: understand → explore → design → save plan |
| `/dev-cycle` | Automated: RED → GREEN → VERIFY → LINT → COMMIT per step, then final review |
| `/run-tests` | Discover and run pytest across all project directories |
| `/python-reviewer` | Static analysis + code review on changes |
| `/review` | AI code review on working tree diff |

## Pipeline Tools

The `/dev-cycle` execution engine lives in `agent_tools/dev_cycle/`. It's a Python program that uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) to spawn sub-agents, with a custom state machine controlling phase transitions and retries:

| File | Purpose |
|------|---------|
| `run.py` | Full pipeline — parse plan, run all steps, final review |
| `run_step.py` | Single step/phase — for decomposed execution |
| `pipeline.py` | Orchestrator — manages step loop and state transitions |
| `state_machine.py` | Phase enum and transition logic |
| `agents.py` | Agent config builders — prompts, tools, model per role |
| `steps.py` | Phase runners — spawns agents via Agent SDK (red, green) or runs subprocess (verify, lint) |
| `checks/` | Static checks, risk scoring, conventions loading |

## Project Structure

```
ai-dev-team-workflow/
├── task_tracker/              ← sample app (the code being developed)
│   ├── pyproject.toml
│   ├── tracker.py
│   └── tests/
├── .claude/
│   ├── agents/                ← sde, test-eng, sys-arch
│   └── skills/                ← plan, dev-cycle, run-tests, python-reviewer, review
├── agent_tools/
│   └── dev_cycle/             ← pipeline engine (Agent SDK)
├── conventions/
│   ├── python-coding.md       ← coding standards (agents reference this)
│   ├── workflow-contract.md   ← TDD phase rules and agent boundaries
│   └── orchestration-flow.md  ← full pipeline architecture docs
├── CLAUDE.md                  ← project rules & code boundaries
└── README.md
```

## Demo Scenario

The `task_tracker/` app is a simple CLI task manager that supports add, list, and complete. The **delete feature is intentionally missing** — that's the task you give to `/plan` to demonstrate the full multi-agent workflow.

```bash
# Step 1: Plan it (interactive — you approve each stage)
/plan "Add delete task feature to task_tracker"

# Step 2: Execute it (automated TDD pipeline)
/dev-cycle plans/<your-plan>.md

# Or run a single phase manually
/dev-cycle plans/<your-plan>.md --step 1 --red
/dev-cycle plans/<your-plan>.md --step 1 --green
/dev-cycle plans/<your-plan>.md --final-review
```

## Adapting for Your Project

1. Replace `task_tracker/` with your own Python project (needs `pyproject.toml`)
2. Adjust `CLAUDE.md` with your project-specific rules and boundaries
3. Edit `conventions/python-coding.md` to match your style
4. Review `conventions/workflow-contract.md` for phase rules and agent boundaries

The agents and skills work with any uv-managed Python project directory.

## Previous Version

The v1 workflow used simpler `/dev-tdd` and `/dev-fast` skills that orchestrated agents inline (no Agent SDK, no state machine). That version is preserved:

- **README:** [`README-v1-tdd-agents.md`](README-v1-tdd-agents.md)
- **Tag:** [`v1-before-refactor`](../../tree/v1-before-refactor) — checkout this tag to get the full v1 codebase

## Part of AI Will Replace You

This repo is part of the experiments I run on [doryzidon.com](https://doryzidon.com) exploring AI workflows and orchestrations for software engineering.

- Blog post: *coming soon*
- YouTube walkthrough: *coming soon*

## License

MIT

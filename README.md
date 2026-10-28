# AI Dev Team Workflow

Multi-agent Python development with [Claude Code](https://claude.ai/claude-code). Specialized AI agents collaborate through slash commands to plan, code, test, and review — like a real engineering team.

## What's New (v3.0.0)

Three skills cover the whole loop: `/plan` designs it, `/dev-cycle` builds it, `/verify` proves it.

- **Simpler pipeline.** Each `/dev-cycle` step now runs IMPLEMENT → VERIFY → REVIEW → COMMIT. One implement agent writes the code and its tests together and runs pytest as it goes, replacing the separate RED and GREEN phases. VERIFY is a single gate: lint plus the full test suite.
- **Explore first.** Before the first step, an explore phase researches the codebase and hands its findings to every step. Skip it with `--no-explore`.
- **Review modes.** `--review-mode static|agent|full` sets how deep reviews go, from static checks only up to an LLM review of every step plus an engineering review of the full diff.
- **Run memory.** The pipeline keeps a vault (`agent_tools/dev_cycle/vault/`) of notes per step: files created, public APIs, test results, decisions. Later steps and reruns of the same plan read it, so context survives between agents.
- **Plans you can verify.** `/plan` maps every acceptance criterion to how it will be proven (method, command, expected result), and also renders a self-contained HTML version of the plan with an SVG diagram.
- **New `/verify` skill and `verifier` agent.** After a run, a separate agent with fresh context checks the change against the plan's verification table and reports PASS or FAIL per criterion, with command output as evidence. It can hand the checks to Codex or Cursor for a second model's view, then re-runs everything itself before it gives a verdict.
- **v1 skills kept for reference.** `/dev-tdd` and `/dev-fast` are back in `.claude/skills/`, marked deprecated.

## v2: TDD Pipeline

v2 replaced the original `/dev-tdd` and `/dev-fast` skills with a two-skill architecture:

- **`/plan`** — interactive research and design (user in the loop)
- **`/dev-cycle`** — automated TDD execution pipeline (headless)

### Why the rewrite?

v1 relied on a single Claude Code session orchestrating everything inline — one prompt juggling planning, test writing, implementation, and review. It worked, but it was brittle and non-deterministic: steps got skipped, agent roles blurred, and there was no way to retry a failed phase or resume from where you left off.

v2 fixes this by separating **planning** (interactive, human-in-the-loop) from **execution** (programmatic, headless). The execution pipeline (`/dev-cycle`) is a Python program with a proper state machine and retry policies. It uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) to spawn isolated sub-agents with strict role boundaries. Each agent gets its own context, tools, and instructions. The orchestrator controls the flow, not the LLM.

> Looking for an older version? See [Previous Versions](#previous-versions).

## Quick Start

```bash
# Clone with submodule
git clone --recurse-submodules https://github.com/DoryZi/ai-dev-team-workflow.git
cd ai-dev-team-workflow

# 1. Plan the feature (interactive)
/plan "Add delete task feature to task_tracker"

# 2. Execute the plan (automated pipeline)
/dev-cycle plans/<your-plan>.md

# 3. Prove it meets the plan's acceptance criteria
/verify plans/<your-plan>.md
```

## Architecture

```
/plan  (interactive, you approve each stage)
  understand → explore → acceptance criteria → verification table → steps
  saves plans/<slug>.md and plans/<slug>.html
        │
        ▼
/dev-cycle  (automated, headless)
  EXPLORE the codebase (once)
  for each step:  IMPLEMENT → VERIFY → REVIEW → COMMIT
  then:           FINAL REVIEW
        │
        ▼
/verify  (separate agent, fresh context)
  runs every row of the plan's verification table
  reports PASS or FAIL per acceptance criterion, with evidence
```

See [`conventions/orchestration-flow.md`](conventions/orchestration-flow.md) for the v2 state machine diagrams (v3 phases are in `agent_tools/dev_cycle/state_machine.py`).

## Agents

| Agent | Role | Used by |
|-------|------|---------|
| **sys-arch** | Systems architect: researches the codebase and designs plans (read-only) | `/plan` |
| **sde** | Staff software engineer: writes production code, runs smoke tests | Direct use |
| **test-eng** | Senior test engineer: writes unit and e2e tests against acceptance criteria | Direct use |
| **verifier** | Verification engineer: proves a change meets the plan's acceptance criteria, never edits production code | `/verify` |

Agents are defined in `.claude/agents/` and enforce strict boundaries: sde never touches tests, test-eng never touches production code, sys-arch never writes files, verifier reports bugs instead of fixing them. The `/dev-cycle` pipeline builds its own headless agents from the prompts in `agent_tools/dev_cycle/prompts/`.

## Skills (Slash Commands)

| Skill | Description |
|-------|-------------|
| `/plan` | Interactive: understand → explore → design → verification table → save plan (markdown + HTML) |
| `/dev-cycle` | Automated: EXPLORE, then IMPLEMENT → VERIFY → REVIEW → COMMIT per step, then final review |
| `/verify` | Checks a finished change against the plan's acceptance criteria, PASS or FAIL per criterion |
| `/run-tests` | Discover and run pytest across all project directories |
| `/python-reviewer` | Static analysis + code review on changes |
| `/review` | AI code review on working tree diff |
| `/dev-tdd`, `/dev-fast` | v1 skills, deprecated, kept for reference |

## Pipeline Tools

The `/dev-cycle` execution engine lives in `agent_tools/dev_cycle/`. It's a Python program that uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) to spawn sub-agents, with a custom state machine controlling phase transitions and retries:

| File | Purpose |
|------|---------|
| `run.py` | Full pipeline: parse plan, explore, run all steps, final review |
| `run_step.py` | Single step or phase, for decomposed execution |
| `pipeline.py` | Orchestrator: manages the step loop and state transitions |
| `state_machine.py` | Phase enum and transition logic |
| `agents.py` | Agent config builders: prompt, tools, and model per role |
| `steps.py` | Phase runners: spawn agents via the Agent SDK or run subprocesses |
| `vault.py` | Run memory: saves notes after each step and loads them before the next |
| `save_explorations.py` | Saves research agent reports so later plans can reuse them |
| `prompts/` | Base prompts for the pipeline agents (explore, implement, review, eng-review) |
| `checks/` | Static checks, risk scoring, conventions loading |

## Project Structure

```
ai-dev-team-workflow/
├── task_tracker/              ← sample app (the code being developed)
│   ├── pyproject.toml
│   ├── tracker.py
│   └── tests/
├── .claude/
│   ├── agents/                ← sys-arch, sde, test-eng, verifier
│   └── skills/                ← plan, dev-cycle, verify, run-tests, python-reviewer, review
│                                 (+ deprecated v1: dev-tdd, dev-fast)
├── agent_tools/
│   └── dev_cycle/             ← pipeline engine (Agent SDK) + vault/
├── conventions/
│   ├── python-coding.md       ← coding standards (agents reference this)
│   ├── workflow-contract.md   ← phase rules and agent boundaries
│   └── orchestration-flow.md  ← full pipeline architecture docs
├── CLAUDE.md                  ← project rules & code boundaries
├── AGENTS.md                  ← agents, skills, and how they fit together
└── README.md
```

## Demo Scenario

The `task_tracker/` app is a simple CLI task manager that supports add, list, and complete. The **delete feature is intentionally missing**. That's the task you give to `/plan` to demonstrate the full multi-agent workflow.

```bash
# Step 1: Plan it (interactive, you approve each stage)
/plan "Add delete task feature to task_tracker"

# Step 2: Execute it (automated pipeline)
/dev-cycle plans/<your-plan>.md

# Or run a single phase manually
/dev-cycle plans/<your-plan>.md --step 1 --implement
/dev-cycle plans/<your-plan>.md --step 1 --verify
/dev-cycle plans/<your-plan>.md --final-review

# Step 3: Verify it against the plan's acceptance criteria
/verify plans/<your-plan>.md
/verify plans/<your-plan>.md --agent codex    # second model writes the checks
```

## Adapting for Your Project

1. Replace `task_tracker/` with your own Python project (needs `pyproject.toml`)
2. Adjust `CLAUDE.md` with your project-specific rules and boundaries
3. Edit `conventions/python-coding.md` to match your style
4. Review `conventions/workflow-contract.md` for phase rules and agent boundaries

The agents and skills work with any uv-managed Python project directory.

## Previous Versions

Each version is preserved as a git tag:

- **v2.0.0** ([`v2.0.0`](../../tree/v2.0.0)): the first `/plan` + `/dev-cycle` pipeline, running RED → GREEN → VERIFY → LINT → COMMIT per step.
- **v1** ([`v1-before-refactor`](../../tree/v1-before-refactor)): the `/dev-tdd` and `/dev-fast` skills that orchestrated agents inline (no Agent SDK, no state machine). README: [`README-v1-tdd-agents.md`](README-v1-tdd-agents.md)

## Part of AI Will Replace You

This repo is part of the experiments I run on [doryzidon.com](https://doryzidon.com) exploring AI workflows and orchestrations for software engineering.

- Blog post: *coming soon*
- YouTube walkthrough: *coming soon*

## License

MIT

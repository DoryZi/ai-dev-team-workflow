# Skill Template

Use this template when creating new skills in `.claude/skills/<name>/SKILL.md`.

## Structure

```markdown
---
name: <skill-name>
description: <one-line description shown in the skill list>
color: <optional: blue, cyan, green, yellow, red>
---

# <Skill Name> — <Short Description>

<One-line summary of what the skill does.>

## Usage

\```
/<skill-name> <arguments>
/<skill-name> "example task description"
/<skill-name> target_dir "example with directory"
\```

## Workflow

### Phase 1: <Name>

What to do in this phase. Be specific about which tools and agents to use:

Use the `Agent` tool:
- `subagent_type`: `<agent-name>`
- `prompt`: <what to tell the agent>

### Phase 2: <Name>

Next phase. If invoking another skill:

Invoke `/<other-skill>` using the Skill tool with the target directory.

### Phase 3: <Name> (loop, max N iterations)

For iterative phases:
1. Run the check
2. If passing → proceed to next phase
3. If failing → fix and re-run
4. Repeat up to N times. If still failing, report and stop.

### Phase N: Report

Present final summary:
\```
## <Skill Name> Complete

Feature: <description>
Status: <outcome>
Files changed: [list]
\```

## Rules

**DO:**
- <specific positive behaviors>
- Use /run-tests for all test execution
- Use /python-reviewer for all reviews

**DON'T:**
- <specific behaviors to avoid>
- Continue past max iterations — report and stop
```

## Key Principles

1. **Frontmatter is required** — `name` and `description` fields; `color` is optional
2. **Usage section** — shows exact invocation syntax with examples
3. **Phases are numbered** — clear progression with named steps
4. **Agent delegation** — skills orchestrate agents, agents do the work
5. **Iteration limits** — every loop has a max count and a "report and stop" fallback
6. **Report phase** — every skill ends with a structured summary
7. **DO/DON'T rules** — explicit boundaries on what the skill can and cannot do

## Skill Types

### Orchestrator skills (e.g., /dev-tdd, /dev-fast)
- Coordinate multiple agents through phases
- Include planning, execution, testing, and review loops
- Always get user approval before writing code

### Utility skills (e.g., /run-tests, /python-reviewer)
- Perform a single focused task
- Called by orchestrators or directly by the user
- Never modify code — report only

## Examples

See `.claude/skills/dev-tdd/SKILL.md` for an orchestrator skill and `.claude/skills/run-tests/SKILL.md` for a utility skill.

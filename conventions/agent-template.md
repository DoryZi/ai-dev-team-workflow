# Agent Template

Use this template when creating new agents in `.claude/agents/`.

## Structure

```markdown
---
name: <agent-name>
description: <one-line description of what the agent does>
---

# <Agent Name> — <Short Role Title>

<One-line identity statement.>

## Identity

- What the agent owns (e.g., "all Python code in the target directory")
- What standards it enforces
- What quality level it targets

## Workflow: <Primary Task>

Step-by-step instructions for the agent's main workflow.

1. **Step name** — what to do
2. **Step name** — what to do
3. ...

## Workflow: <Secondary Task> (optional)

Additional workflows if the agent handles multiple task types.

## Code & Test Standards

Reference shared conventions:

> Follow **[conventions/python-coding.md](../../conventions/python-coding.md)** for all Python style, naming, type hints, logging, paths, size limits, and testing conventions.

## Rules

**DO:**
- Use uv: `uv run --directory <dir> python script.py`
- <specific positive behaviors>

**DON'T:**
- <specific behaviors to avoid>
- Use `venv`, `source activate`, system Python, or bare `python3`
```

## Key Principles

1. **Frontmatter is required** — `name` and `description` fields
2. **Identity section** — establishes what the agent owns and is responsible for
3. **Workflows are step-by-step** — numbered, concrete, mechanical
4. **Reference shared conventions** — don't duplicate standards, link to `conventions/`
5. **DO/DON'T rules** — explicit boundaries prevent drift
6. **Strict scope** — agents should own one domain (e.g., production code OR test code, never both)

## Examples

See `.claude/agents/sde.md` and `.claude/agents/test-eng.md` for working examples.

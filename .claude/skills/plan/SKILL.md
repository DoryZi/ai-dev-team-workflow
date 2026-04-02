---
name: plan
description: Interactive research and design skill. Explores the codebase with sys-arch agents, designs acceptance criteria and implementation steps with user approval at every stage.
---

# Plan

Research a codebase and design an implementation plan interactively. The user is in the loop at every stage — never auto-advance without explicit approval.

## Usage

```
/plan "Add retry logic with exponential backoff to youtube_upload.py"
/plan "Refactor the buffer API to support rate limiting"
/plan "Add a new transcription backend using local Whisper"
```

## Workflow

### Stage 1: Understand (interactive)

Ask clarifying questions about the request before doing any research:
- What is the expected behavior?
- What are the constraints (performance, compatibility, etc.)?
- What should happen on error?
- What is the scope — is this a small fix or a large feature?

**Do NOT proceed until the user confirms your understanding is correct.** This may take multiple rounds of Q&A. It's better to ask too many questions than to build a plan on wrong assumptions.

### Stage 2: Explore (parallel agents)

Based on the scope, determine how many dimensions to research:

| Scope | Agents | Dimensions |
|-------|--------|------------|
| Small, isolated change | 1 | modules |
| Moderate change | 2 | modules + patterns |
| Large, multi-area feature | 3-4 | modules + dependencies + patterns + boundaries |

Spawn sys-arch agents in parallel using the `Agent` tool:

```
For each dimension, launch an Agent with:
- subagent_type: "sys-arch"
- prompt: "Explore the <dimension> dimension of the codebase for <feature>. 
           Focus on <specific areas>. Return structured markdown with file paths 
           and line numbers for every finding."
```

**Launch all agents in a single message** to run them concurrently.

After agents complete, synthesize findings and present to the user:
- What existing code is relevant
- What patterns are already in use
- What utilities can be reused
- Any risks or gotchas

**Ask: "Does this match your understanding? Anything missing or incorrect?"**
Wait for confirmation before proceeding.

### Stage 3: Design (iterative)

#### 3a. Acceptance Criteria

Draft acceptance criteria based on the exploration findings and user requirements. Each criterion must be:
- **Testable** — maps directly to one or more test assertions
- **Specific** — no vague statements like "it works" or "errors are handled"
- **Complete** — covers happy path, error cases, and edge cases

Present to the user. The user may:
- Approve as-is
- Add new criteria
- Remove or modify criteria
- Ask for clarification

**Iterate until the user explicitly approves the acceptance criteria.**

#### 3b. Implementation Steps

Design numbered implementation steps. For each step:
- **Title** — short description
- **Description** — what this step accomplishes
- **Files** — which files to create/modify (optional for large tasks — SDE decides)
- **Test classification** — unit, e2e, or both
- **AC mapping** — which acceptance criteria this step addresses

**Adapt detail level to task size:**
- **Small tasks**: specific files, function signatures, exact changes
- **Large tasks**: high-level steps describing sub-systems. SDE decides file-level design during execution.

Present to the user. The user may:
- Approve as-is
- Reorder steps
- Split or merge steps
- Add or remove steps
- Ask for more detail on specific steps

**Iterate until the user explicitly approves the implementation steps.**

### Stage 4: Save

1. Write the plan to `plans/<slug>-YYYY-MM-DD.md` with this structure:

```markdown
# <Feature Title>

## Acceptance Criteria

- [ ] AC 1
- [ ] AC 2
- [ ] AC 3

## Step 1 — <Title>

<Description>

Files:
- `path/to/file.py`

Test classification: unit

- AC: AC 1

## Step 2 — <Title>

...
```

2. Save exploration reports for future reuse:
```bash
uv run --directory agent_tools/dev_cycle python save_explorations.py \
  --feature "<slug>" \
  --reports <report_files> \
  --dimensions <dimensions>
```

3. Tell the user:
```
Plan saved to plans/<slug>-YYYY-MM-DD.md

To execute: /dev-cycle plans/<slug>-YYYY-MM-DD.md
```

## Rules

**DO:**
- Ask clarifying questions before exploring
- Launch sys-arch agents in parallel (single message, multiple Agent tool calls)
- Present findings and ask for confirmation at every stage
- Iterate on ACs and steps until the user explicitly approves
- Adapt plan detail to task size
- Save exploration reports for reuse

**DON'T:**
- Auto-advance between stages without user approval
- Skip the understanding phase — wrong assumptions waste everyone's time
- Write production code or test files — that's /dev-cycle's job
- Over-specify large tasks (let SDE make design calls)
- Under-specify small tasks (SDE needs clear direction)
- Make assumptions about the user's intent — ask

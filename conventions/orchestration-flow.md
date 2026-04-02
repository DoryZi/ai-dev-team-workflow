# Orchestration Flow

How the TDD development pipeline works end-to-end. This document covers the two-skill architecture, state machines, agent roles, and a complete example run.

For binding rules and conventions, see `conventions/workflow-contract.md`.

---

## Two-Skill Architecture

The orchestration is split into two distinct skills with clear responsibilities:

```
/plan (interactive)          /dev-cycle (automated)
┌─────────────────────┐      ┌─────────────────────────┐
│ Research & Design    │      │ Execution               │
│                     │      │                         │
│ • Understand task   │      │ • Write tests (RED)     │
│ • Explore codebase  │  →   │ • Write code (GREEN)    │
│ • Define ACs        │ plan │ • Run tests (VERIFY)    │
│ • Design steps      │ file │ • Lint (LINT)           │
│ • Save plan         │      │ • Commit (COMMIT)       │
│                     │      │ • Final review          │
│ User in the loop    │      │ Headless execution      │
└─────────────────────┘      └─────────────────────────┘
```

---

## `/plan` State Machine

Interactive and iterative. The user approves each stage before the next begins.

```
┌─────────────────────────────────────────────────┐
│                   UNDERSTAND                     │
│                                                 │
│  Ask clarifying questions about the request     │
│  Scope, constraints, expected behavior          │
│  Multiple rounds of Q&A allowed                 │
│                                                 │
│  Exit: user confirms understanding is correct   │
└────────────────────┬────────────────────────────┘
                     │ user approval
                     ▼
┌─────────────────────────────────────────────────┐
│                    EXPLORE                       │
│                                                 │
│  Spawn 1-4 sys-arch agents IN PARALLEL:         │
│  ┌─────────────┐ ┌──────────────┐               │
│  │  modules    │ │ dependencies │               │
│  └─────────────┘ └──────────────┘               │
│  ┌─────────────┐ ┌──────────────┐               │
│  │  patterns   │ │  boundaries  │               │
│  └─────────────┘ └──────────────┘               │
│                                                 │
│  Agent count based on scope:                    │
│  • 1 agent — small, isolated change             │
│  • 2 agents — moderate change                   │
│  • 3-4 agents — large, multi-area feature       │
│                                                 │
│  Present findings → user confirms / adds context│
└────────────────────┬────────────────────────────┘
                     │ user approval
                     ▼
┌─────────────────────────────────────────────────┐
│                    DESIGN                        │
│                                                 │
│  Draft acceptance criteria → user refines       │
│  ↻ iterate until user approves ACs              │
│                                                 │
│  Design implementation steps → user refines     │
│  ↻ iterate until user approves steps            │
│                                                 │
│  Steps may be high-level or file-specific       │
│  depending on task size                         │
└────────────────────┬────────────────────────────┘
                     │ user approval
                     ▼
┌─────────────────────────────────────────────────┐
│                     SAVE                         │
│                                                 │
│  Save plan → plans/<slug>-YYYY-MM-DD.md         │
│  Save explorations → code_explorations/         │
│  Tell user: /dev-cycle plans/<slug>.md           │
└─────────────────────────────────────────────────┘
```

---

## `/dev-cycle` State Machine

Automated execution. Runs headless per step, then a final review.

```
                    ┌──────────────┐
                    │  Parse Plan  │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │     For each step:      │
              │                         │
              │  ┌─────┐                │
              │  │ RED │ test-eng       │
              │  │     │ writes tests   │
              │  └──┬──┘                │
              │     │                   │
              │  ┌──▼────┐              │
              │  │ GREEN │ sde          │
              │  │       │ implements   │
              │  └──┬────┘              │
              │     │                   │
              │  ┌──▼─────┐             │
              │  │ VERIFY │ run pytest  │
              │  │        │             │
              │  └──┬─────┘             │
              │     │ fail?             │
              │     ├──→ sde fixes      │
              │     │    (max 3)        │
              │     │                   │
              │  ┌──▼───┐              │
              │  │ LINT  │ ruff format  │
              │  │       │ ruff check   │
              │  └──┬────┘              │
              │     │ fail?             │
              │     ├──→ auto-fix       │
              │     │    (max 3)        │
              │     │                   │
              │  ┌──▼─────┐            │
              │  │ COMMIT │ git commit  │
              │  └────────┘             │
              │                         │
              └────────────┬────────────┘
                           │ all steps done
                           ▼
              ┌────────────────────────┐
              │     FINAL REVIEW       │
              │                        │
              │  1. Static checks      │
              │     (file size, print, │
              │      secrets, func     │
              │      length)           │
              │                        │
              │  2. /review on full    │
              │     branch diff        │
              │     (with static       │
              │      scores as         │
              │      context)          │
              │                        │
              │  Verdict:              │
              │  APPROVE → create PR   │
              │  BLOCK → report to     │
              │           user         │
              └────────────────────────┘
```

### Phase transitions

| From | To | Condition |
|------|----|-----------|
| RED | GREEN | Tests written and committed |
| GREEN | VERIFY | Code implemented |
| VERIFY | LINT | All tests pass (or max 3 retries exhausted) |
| LINT | COMMIT | Lint clean (or max 3 retries exhausted) |
| COMMIT | RED (next step) | Step committed |
| COMMIT (last step) | FINAL_REVIEW | All steps done |

### Retry policies

| Phase | Max retries | On failure |
|-------|-------------|------------|
| VERIFY | 3 | SDE fixes production code, re-run pytest |
| LINT | 3 | Auto-fix with ruff, re-check |
| FINAL_REVIEW | 0 | Report findings to user, stop |

---

## Agent Roles

| Agent | Used by | Tools | Responsibility |
|-------|---------|-------|---------------|
| sys-arch | `/plan` | Read, Glob, Grep (read-only) | Research codebase, design systems, produce plans |
| test-eng | `/dev-cycle` | Read, Write, Edit, Bash, Glob, Grep | Write failing tests (RED phase) |
| sde | `/dev-cycle` | Read, Write, Edit, Bash, Glob, Grep | Implement production code (GREEN phase), fix failures |

### Boundary rules

- **sys-arch** never writes files — read-only exploration and design
- **test-eng** never modifies production code — if it finds a bug, it reports it
- **sde** never modifies test files — tests are the spec, not the implementation
- These boundaries are always strict, regardless of task size

---

## Example Run

### 1. Plan the feature

```
User: /plan "Add retry logic with exponential backoff to youtube_upload.py"

/plan UNDERSTAND:
  "What should happen after all retries are exhausted? Raise the original error,
   or a custom RetryExhaustedError? And should we retry on all exceptions or
   only network-related ones?"

User: "Raise RetryExhaustedError with the last exception as cause. Only retry
       on ConnectionError and TimeoutError."

/plan EXPLORE:
  Spawns 2 sys-arch agents (modules + patterns)
  → modules agent: finds youtube_upload.py structure, existing error handling
  → patterns agent: finds retry patterns in other tools (buffer_api has similar)

  "Here's what I found: youtube_upload.py has no retry logic. buffer_api/schedule_post.py
   has a simple retry loop at line 45 we could follow. Want me to proceed?"

User: "Yes, looks good."

/plan DESIGN:
  Acceptance Criteria:
  1. upload_video() retries on ConnectionError and TimeoutError
  2. Backoff is exponential: 1s, 2s, 4s (3 attempts)
  3. After 3 failures, raises RetryExhaustedError with last exception as __cause__
  4. Each retry attempt is logged with structured context

  Steps:
  1. Add RetryExhaustedError and retry decorator to youtube_upload.py
  2. Integrate retry into upload_video() function

User: "Approved."

/plan SAVE:
  → plans/youtube-retry-2026-04-01.md
  "Run: /dev-cycle plans/youtube-retry-2026-04-01.md"
```

### 2. Execute the pipeline

```
User: /dev-cycle plans/youtube-retry-2026-04-01.md

Step 1/2: Add RetryExhaustedError and retry decorator
  RED   — test-eng writes 6 tests (happy path, exhaustion, specific exceptions, logging)
  GREEN — sde implements RetryExhaustedError class + retry decorator
  VERIFY — pytest: 6 passed ✓
  LINT   — ruff: clean ✓
  COMMIT — "Add tests for retry logic" + "Implement retry decorator"

Step 2/2: Integrate retry into upload_video()
  RED   — test-eng writes 4 tests (upload with retry, upload success on 2nd try, etc.)
  GREEN — sde adds @retry decorator to upload_video()
  VERIFY — pytest: 10 passed ✓
  LINT   — ruff: clean ✓
  COMMIT — "Add tests for upload retry" + "Integrate retry into upload_video"

FINAL REVIEW:
  Static checks: 0 violations ✓
  /review: APPROVE — no findings
  → PR created
```

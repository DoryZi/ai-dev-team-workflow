---
name: dev-cycle
description: Execute a plan through the TDD pipeline — RED/GREEN/VERIFY/LINT per step, then final review with static checks + /review. Deterministic, headless-capable.
---

# Dev Cycle

Execute an implementation plan through the TDD pipeline. Each step goes through RED → GREEN → VERIFY → LINT → COMMIT, followed by a final review (static checks + /review).

## Usage

```
/dev-cycle plans/foo.md                              # full pipeline
/dev-cycle plans/foo.md --step 3                     # resume from step 3
/dev-cycle plans/foo.md --step 3 --green             # just green for step 3
/dev-cycle plans/foo.md --step 3 --red               # just red for step 3
/dev-cycle plans/foo.md --step 3 --verify            # just verify for step 3
/dev-cycle plans/foo.md --step 3 --lint              # just lint for step 3
/dev-cycle plans/foo.md --step 3 --commit            # just commit for step 3
/dev-cycle plans/foo.md --final-review               # just final review (full diff)
/dev-cycle plans/foo.md --max-verify 5               # more verify retries
/dev-cycle plans/foo.md --dry-run                    # validate plan only
```

## Workflow

### 1. Parse Arguments

From `$ARGUMENTS`, extract:
- **Plan path** — required (first positional arg, or infer from conversation context)
- **--step N** — optional, resume from step N
- **--red / --green / --verify / --lint / --commit / --final-review** — optional, run single phase
- **--max-verify N** — override max verify attempts (default 3)
- **--max-lint N** — override max lint attempts (default 3)
- **--dry-run** — validate plan structure only

### 2. Run the Pipeline

**Full pipeline** (no phase flag):
```bash
uv run --directory agent_tools/dev_cycle python run.py \
  --plan <plan_path> \
  [--step N] \
  [--max-verify N] \
  [--max-lint N] \
  [--dry-run]
```

**Single phase** (phase flag present):
```bash
uv run --directory agent_tools/dev_cycle python run_step.py \
  --plan <plan_path> \
  --step N \
  --phase <red|green|verify|lint|commit|final-review> \
  [--context "extra instructions for the agent"]
```

Phase flag mapping: `--red` → `red`, `--green` → `green`, `--verify` → `verify`, `--lint` → `lint`, `--commit` → `commit`, `--final-review` → `final-review`.

### 3. Present Results

Read the structured JSON output from stdout. Present to the user:
- Per-step status (pass/fail, attempts, cost)
- Any lint violations or test failures
- Final review verdict
- PR URL if created
- Total cost

If running decomposed (single phase), present the phase result and **automatically continue to the next phase in the cycle** unless the user explicitly stops you. The full per-step cycle is: RED → GREEN → VERIFY → LINT → COMMIT. Never stop after VERIFY or LINT without committing — every step must complete the full cycle through COMMIT.

### 4. Handle Failures

If the pipeline fails:
- Show which step and phase failed
- Show the failure details (test output, lint violations)
- List all steps from the plan with their status so the user can pick where to resume:
  ```
  ## Steps
  1. Add retry decorator              ✓ done
  2. Integrate retry into upload       ✗ FAILED (verify — 2 tests failing)
  3. Add structured logging            - pending

  Resume from step 2:
  /dev-cycle plans/foo.md --step 2
  /dev-cycle plans/foo.md --step 2 --green   (skip red, tests already written)
  ```

## Rules

- Always check that `agent_tools/dev_cycle` is set up: `cd agent_tools/dev_cycle && uv sync`
- Resolve plan paths relative to the repo root
- When no plan is specified, look for the most recent plan in conversation context
- When no step is specified for a phase flag, infer from conversation context
- Present cost summaries after each step completes
- Do not modify the pipeline code — just call it

---
name: verify
description: Prove a change satisfies its plan's acceptance criteria. Hands the change and the plan's verification mapping to a verifier subagent that writes and runs verification in its own context, and reports PASS/FAIL per criterion. The verifier driver is pluggable — claude (default), codex, or cursor.
---

# Verify

Prove that an implemented change actually does what its plan said it would. This
runs *after* `/dev-cycle` (or any implementation), against the acceptance criteria
and Verification table the `/plan` skill produced.

The verification work runs in a **separate context** — a `verifier` subagent. That
subagent does not see this conversation; it gets a self-contained brief. This keeps
verification honest (it can't lean on context that biases it toward "it works") and
keeps your main context clean.

## Usage

```
/verify plans/<slug>-YYYY-MM-DD.md
/verify plans/<slug>-YYYY-MM-DD.md --agent codex
/verify plans/<slug>-YYYY-MM-DD.md --agent cursor
/verify plans/<slug>-YYYY-MM-DD.md --agent claude --dir task_tracker
```

- **First arg** — the plan file (or, if omitted, ask which plan / which criteria to verify).
- **`--agent`** — the verifier driver: `claude` (default), `codex`, or `cursor`.
- **`--dir`** — target directory of the code under test, if not inferable from the plan.

## Drivers

| `--agent` | Who writes & runs the verification | Notes |
|-----------|------------------------------------|-------|
| `claude` (default) | The verifier subagent, directly | The standard flow. |
| `codex` | Codex CLI (`codex exec`), then the verifier re-runs to confirm | Independent, cross-model. |
| `cursor` | Cursor CLI (`cursor-agent -p`), then the verifier re-runs to confirm | Independent, cross-model. |

With `codex`/`cursor`, the external agent writes and runs verification in its own
sandbox, but the **verdict is always the verifier's**, based on commands it re-ran
itself. An external "PASS" is a signal, not the answer. Use these drivers when you
want a second model's eyes — cross-model verification, not self-grading.

**Availability:** `codex` and `cursor` require their CLIs installed and
authenticated (`codex`, `cursor-agent`). If `--agent codex|cursor` is requested but
the CLI is missing, tell the user and offer to fall back to `claude` — do not
silently substitute.

## Workflow

### 1. Resolve inputs
- Read the plan file. Extract the **Acceptance Criteria** and the **Verification**
  table (AC → Method → Command → Expected result).
- Determine the target directory (`--dir`, or infer from the plan's Files lists).
- Determine the driver (`--agent`, default `claude`).
- If the plan has no Verification table, say so — the verifier will derive one, but
  flag that the criteria weren't pre-mapped.

### 2. Pre-flight (codex/cursor only)
If the driver is `codex` or `cursor`, confirm the CLI exists:
```bash
command -v codex        # for --agent codex
command -v cursor-agent # for --agent cursor
```
If missing, stop and ask the user whether to fall back to `claude`.

### 3. Launch the verifier subagent
Spawn one `verifier` agent with the `Agent` tool:

```
subagent_type: "verifier"
prompt: |
  Verify the implementation against this plan: <plan path>
  Target directory: <dir>
  Driver: <claude|codex|cursor>

  The plan's Verification table is your spec. For each acceptance criterion,
  write/run the verification, run every command in the table, and report PASS/FAIL
  per criterion with the actual command output as evidence. Do not modify
  production code — report code bugs as findings. If the driver is codex or cursor,
  delegate the writing/running to that CLI, then independently re-run the
  verification commands yourself and base the verdict on YOUR runs.
```

### 4. Relay the result
The verifier's report is returned to you (not shown to the user directly). Present:
- The per-criterion PASS/FAIL checklist
- Any code bugs found (file:line)
- For codex/cursor: whether the external agent's claims matched the verifier's re-run
- Overall status: **ALL CRITERIA PASS** or **N FAILING**

If criteria failed due to code bugs, surface them clearly and ask the user whether
to loop back to `/dev-cycle` to fix them.

## Rules

**DO:**
- Run verification in the `verifier` subagent's own context, not inline.
- Use the plan's Verification table as the spec — verify every row.
- Default to the `claude` driver; use `codex`/`cursor` only when asked.
- Confirm the external CLI exists before selecting it; offer fallback, never silent-substitute.
- Base the final verdict on commands the verifier actually re-ran.
- Surface code bugs with file:line and offer the loop back to `/dev-cycle`.

**DON'T:**
- Let the verifier modify production code.
- Report PASS without a command and observable result behind each criterion.
- Trust an external agent's PASS without an independent re-run.
- Silently swap drivers if the requested CLI is unavailable.
- Verify against vague criteria — if a criterion isn't testable, say so (UNVERIFIABLE).

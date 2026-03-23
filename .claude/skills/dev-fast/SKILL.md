---
name: dev-fast
description: Fast development workflow. Plan → write code → write tests → run tests → fix loop → review → verify. Uses sde, test-eng, run-tests, and python-reviewer.
color: cyan
---

# Dev Fast — Code-First Development Workflow

Fast development cycle: plan the feature, write code, then write tests to verify, review, and confirm.

## Usage

```
/dev-fast <task description>
/dev-fast "Add retry logic to youtube_upload.py"
/dev-fast agent_tools/buffer_api "Add rate limiting support"
/dev-fast task_tracker "Add delete task feature"
```

## Workflow

### Phase 1: Plan

Enter plan mode to design the implementation approach.

Use the `Agent` tool:
- `subagent_type`: `sde`
- `prompt`: Ask the sde agent to analyze the target code and produce an implementation plan for the requested feature. The plan should cover:
  - What files will be created/modified
  - Key functions and their signatures
  - Edge cases to handle
  - Dependencies needed
- Do NOT write any code yet — plan only.

Present the plan to the user. Wait for approval before proceeding.

### Phase 2: Write Code (sde)

Use the `Agent` tool:
- `subagent_type`: `sde`
- `prompt`: Pass the approved plan. Ask sde to implement the feature following the plan.

### Phase 3: Write Tests (test-eng)

Use the `Agent` tool:
- `subagent_type`: `test-eng`
- `prompt`: Pass the target directory. Ask test-eng to analyze the code that was just written and write comprehensive tests covering happy path, error cases, and edge cases.

### Phase 4: Test Loop (max 3 iterations)

1. Invoke `/run-tests` using the Skill tool with the target directory.
2. If all tests pass → proceed to Phase 5.
3. If tests fail:
   - Use the `Agent` tool with `subagent_type`: `sde`
   - Pass the test failure output
   - Ask it to fix the production code (NOT the tests) to make failing tests pass
   - Re-run `/run-tests`
4. Repeat up to 3 times. If still failing after 3 iterations, report status to user and stop.

### Phase 5: Code Review Loop (max 3 iterations)

1. Invoke `/python-reviewer` using the Skill tool.
2. If verdict is **APPROVE** → proceed to Phase 6.
3. If verdict is **BLOCK** or **WARNING**:
   - Pass the DO/DON'T findings directly to the `sde` agent. The DO/DON'T format gives sde exact before/after code — it should apply the "DO" fixes.
   - Use the `Agent` tool with `subagent_type`: `sde`
   - In the prompt, include the full DO/DON'T report and ask it to apply all the "DO" fixes for CRITICAL and HIGH issues
   - Run `/run-tests` to make sure fixes didn't break tests
   - Re-run `/python-reviewer`
4. Repeat until APPROVE or max 3 iterations. If still not APPROVE, present the remaining findings to the user and stop.

### Phase 6: Final Verification

Invoke `/run-tests` using the Skill tool one final time to confirm nothing broke during the review fixes.

If tests fail:
1. Use the `Agent` tool with `subagent_type`: `sde` to fix
2. Re-run `/run-tests`
3. Repeat until green (max 2 iterations)

### Phase 7: Report

Present final summary:
```
## Dev Fast Complete

Feature: <description>
Plan: APPROVED
Code written: [files]
Tests written: X files, Y test cases
Tests: ALL PASSING
Review: APPROVE | WARNING (details)
Files changed: [list]
```

## Rules

**DO:**
- Always get plan approval before writing any code
- Write code first, then tests (code-first approach)
- Only let sde modify production code
- Only let test-eng write tests
- Use /run-tests for all test execution
- Use /python-reviewer for all reviews

**DON'T:**
- Skip the planning phase
- Let sde modify test files
- Let test-eng modify production code
- Continue past max iterations — report and stop
- Skip the final verification after review fixes

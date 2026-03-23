---
name: review
description: Run an AI code review on the current working tree changes. Use when the user wants to review their code, check for issues, or get feedback before committing.
argument-hint: [--staged | --branch <name> | --provider openai | <file>]
allowed-tools: Read, Grep, Glob, Bash(git diff*), Bash(source venv/bin/activate*)
---

# AI Code Review

Review the current code changes for bugs, security issues, performance problems, style violations, and missing error handling.

## Provider routing

Check `$ARGUMENTS` for `--provider openai`:

- **If `--provider openai` is present**: Run the review via the local_review script, passing all arguments through:
  ```
  source venv/bin/activate && python3 -m agent_tools.code_review.local_review $ARGUMENTS
  ```
  Then display the output to the user. Do NOT review the code yourself.

- **Otherwise**: Claude reviews the code directly (continue with the steps below).

## What to review (Claude mode)

Determine the scope based on `$ARGUMENTS`:

- **No arguments**: Review all uncommitted changes (`git diff HEAD`)
- **`--staged`**: Review only staged changes (`git diff --cached`)
- **`--branch <name>`**: Review changes vs. that branch (`git diff <name>...HEAD`)
- **A file path**: Review only that specific file's changes

## Steps

1. Get the diff using `git diff` based on the scope above.
2. If the diff is empty, tell the user there are no changes to review.
3. Read the changed files to understand the full context around the diff.
4. Review the changes for:
   - **Bugs and logic errors** — off-by-ones, null refs, wrong conditions
   - **Security vulnerabilities** — injection, hardcoded secrets, unsafe input
   - **Performance issues** — unnecessary loops, missing indexes, N+1 queries
   - **Code style** — naming, structure, docstring standards from CLAUDE.md
   - **Missing error handling** — uncaught exceptions, silent failures
5. Present findings sorted by severity.

## Output format

For each finding, report:

```
[severity/category] file:line
Description of the issue.

Don't:
<the current problematic code>

Do:
<the suggested fix>
```

Severities: `critical`, `warning`, `suggestion`, `nitpick`
Categories: `bug`, `security`, `performance`, `style`, `testing`, `logic`

If the code looks good, say so — don't invent problems.

## Rules

- Only comment on added or modified lines, not existing code.
- Be specific and actionable — say what's wrong and how to fix it.
- Keep do/don't examples short (1-5 lines each).
- Limit to the 15 most important findings.
- Follow the docstring standard defined in CLAUDE.md.

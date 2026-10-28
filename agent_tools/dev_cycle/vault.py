"""Obsidian-style vault for persisting run context between pipeline steps.

Saves structured markdown notes after each step with files created, public
API signatures, test results, and agent decisions. Before each step, loads
context from the current run's prior steps and the last completed run of
the same plan.

Vault structure::

    vault/
      <plan-slug>/
        <run-timestamp>/
          step-1-models-and-structure.md
          step-2-actionability.md
          run-summary.md
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from schemas import StepResult

logger = logging.getLogger(__name__)

_VAULT_DIR = Path(__file__).parent / "vault"


@dataclass
class StepNote:
    """A vault note for a single pipeline step.

    Attributes:
        step_number: Step number from the plan.
        title: Step title.
        files_created: Source files created or modified.
        test_files: Test files written.
        public_apis: Extracted public function/class signatures.
        test_count: Number of tests that ran.
        test_passed: Whether all tests passed.
        attempts: Number of verify attempts used.
        implement_output: Full agent output from the IMPLEMENT phase.
        fix_outputs: Agent outputs from IMPLEMENT fix iterations (verify + review loops).
        verify_failures: Final verify failure messages (empty if passed).
        review_findings: Review findings as formatted strings.
    """

    step_number: int = 0
    title: str = ""
    files_created: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    public_apis: list[str] = field(default_factory=list)
    test_count: int = 0
    test_passed: bool = False
    attempts: int = 0
    implement_output: str = ""
    fix_outputs: list[str] = field(default_factory=list)
    verify_failures: list[str] = field(default_factory=list)
    review_findings: list[str] = field(default_factory=list)


@dataclass
class RunManifest:
    """Manifest for a full pipeline run.

    Attributes:
        plan_slug: Slug derived from the plan file name.
        run_id: Timestamp-based run identifier.
        plan_path: Path to the plan file.
        started_at: ISO timestamp when the run started.
        steps_completed: List of step numbers that completed.
        total_tests: Total test count across all steps.
        total_cost_usd: Total agent SDK cost.
    """

    plan_slug: str = ""
    run_id: str = ""
    plan_path: str = ""
    started_at: str = ""
    steps_completed: list[int] = field(default_factory=list)
    total_tests: int = 0
    total_cost_usd: float = 0.0


def plan_slug(plan_path: str) -> str:
    """Derive a slug from a plan file path.

    Args:
        plan_path: Path to the plan markdown file.

    Returns:
        Slug string suitable for directory names.
    """
    name = Path(plan_path).stem
    return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")


def start_run(plan_path: str) -> RunManifest:
    """Create a new run manifest.

    Args:
        plan_path: Path to the plan file.

    Returns:
        RunManifest with slug and timestamp set.
    """
    now = datetime.now(timezone.utc)
    slug = plan_slug(plan_path)
    run_id = now.strftime("%Y%m%d-%H%M%S")

    manifest = RunManifest(
        plan_slug=slug,
        run_id=run_id,
        plan_path=plan_path,
        started_at=now.isoformat(),
    )

    # Create the run directory
    run_dir = _VAULT_DIR / slug / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("[VAULT] Started run %s/%s", slug, run_id)

    return manifest


def _run_dir(manifest: RunManifest) -> Path:
    """Get the directory for a run.

    Args:
        manifest: The run manifest.

    Returns:
        Path to the run directory.
    """
    return _VAULT_DIR / manifest.plan_slug / manifest.run_id


def _step_filename(step_number: int, title: str) -> str:
    """Build a filename for a step note.

    Args:
        step_number: Step number.
        title: Step title.

    Returns:
        Filename like ``step-1-models-and-structure.md``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"step-{step_number}-{slug}.md"


def save_step_note(
    manifest: RunManifest,
    step_result: StepResult,
    cwd: str,
    implement_output: str = "",
    fix_outputs: list[str] | None = None,
) -> Path:
    """Save a vault note after a step completes.

    Auto-extracts public API signatures from created files.

    Args:
        manifest: The current run manifest.
        step_result: Result from the completed step.
        cwd: Repository root for reading source files.
        implement_output: Full agent output from IMPLEMENT phase.
        fix_outputs: Agent outputs from fix iterations (verify + review loops).

    Returns:
        Path to the saved note file.
    """
    run_path = _run_dir(manifest)
    run_path.mkdir(parents=True, exist_ok=True)

    files_created = step_result.implement.changed_files if step_result.implement else []
    test_files = step_result.implement.test_files if step_result.implement else []
    test_count = step_result.verify.num_tests if step_result.verify else 0
    test_passed = step_result.verify.passed if step_result.verify else False

    # Collect verify failures
    verify_failures: list[str] = []
    if step_result.verify and not step_result.verify.passed:
        verify_failures = step_result.verify.failures

    # Collect review findings
    review_findings: list[str] = []
    if step_result.review and step_result.review.findings:
        review_findings = [
            f"[{f.severity}] {f.file}:{f.line} — {f.title}: {f.detail}"
            for f in step_result.review.findings
        ]

    public_apis = extract_public_apis(files_created, cwd)

    note = StepNote(
        step_number=step_result.step_number,
        title=step_result.title,
        files_created=files_created,
        test_files=test_files,
        public_apis=public_apis,
        test_count=test_count,
        test_passed=test_passed,
        attempts=step_result.attempts,
        implement_output=implement_output,
        fix_outputs=fix_outputs or [],
        verify_failures=verify_failures,
        review_findings=review_findings,
    )

    # Write markdown
    filename = _step_filename(note.step_number, note.title)
    note_path = run_path / filename
    note_path.write_text(_render_step_note(note), encoding="utf-8")

    manifest.steps_completed.append(note.step_number)

    logger.info("[VAULT] Saved step note: %s", note_path)
    return note_path


def save_run_summary(
    manifest: RunManifest,
    total_cost_usd: float = 0.0,
    status: str = "success",
    failure_detail: str | None = None,
) -> Path:
    """Save a run summary note after the pipeline completes.

    Args:
        manifest: The run manifest.
        total_cost_usd: Total cost across all steps.
        status: Overall run status.
        failure_detail: Description of what failed, if any.

    Returns:
        Path to the saved summary file.
    """
    run_path = _run_dir(manifest)
    run_path.mkdir(parents=True, exist_ok=True)

    manifest.total_cost_usd = total_cost_usd

    lines = [
        f"# Run Summary: {manifest.plan_slug}",
        "",
        f"- **Run ID**: {manifest.run_id}",
        f"- **Plan**: {manifest.plan_path}",
        f"- **Started**: {manifest.started_at}",
        f"- **Status**: {status}",
        f"- **Steps completed**: {manifest.steps_completed}",
        f"- **Total cost**: ${total_cost_usd:.4f}",
    ]

    if failure_detail:
        lines.extend(["", f"## Failure", "", failure_detail])

    # Read step notes and include summaries
    step_notes = sorted(run_path.glob("step-*.md"))
    if step_notes:
        lines.extend(["", "## Step Summaries", ""])
        for note_path in step_notes:
            content = note_path.read_text(encoding="utf-8")
            # Extract just the header and key stats
            header_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            header = header_match.group(1) if header_match else note_path.stem
            lines.append(f"- **{header}** — see [{note_path.name}]({note_path.name})")

    summary_path = run_path / "run-summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    logger.info("[VAULT] Saved run summary: %s", summary_path)
    return summary_path


def load_context_for_step(
    plan_path: str,
    current_manifest: RunManifest | None,
    step_number: int,
    max_prior_runs: int = 2,
) -> str:
    """Load vault context to inject into agent prompts.

    Gathers context from:
    1. Current run's prior step notes.
    2. Last N completed runs of the same plan.

    Args:
        plan_path: Path to the plan file.
        current_manifest: The current run's manifest (for reading prior steps).
        step_number: The step about to be executed.
        max_prior_runs: Maximum number of prior runs to include.

    Returns:
        Markdown-formatted context string, or empty string if no context.
    """
    slug = plan_slug(plan_path)
    plan_dir = _VAULT_DIR / slug

    if not plan_dir.exists():
        return ""

    sections: list[str] = []

    # 1. Current run's prior steps
    if current_manifest:
        current_dir = _run_dir(current_manifest)
        if current_dir.exists():
            current_notes = _load_step_notes_before(current_dir, step_number)
            if current_notes:
                sections.append("### Current Run — Prior Steps\n")
                sections.append(current_notes)

    # 2. Prior completed runs
    prior_runs = _find_prior_runs(plan_dir, exclude_run_id=current_manifest.run_id if current_manifest else None)
    for run_dir in prior_runs[:max_prior_runs]:
        run_id = run_dir.name
        notes = _load_step_notes_summary(run_dir)
        if notes:
            sections.append(f"### Prior Run ({run_id})\n")
            sections.append(notes)

    # 3. Fix audit trail — lessons from prior bugs
    fixes_dir = _VAULT_DIR / "fixes"
    if fixes_dir.exists():
        fix_notes = []
        for fix_path in sorted(fixes_dir.glob("*.md")):
            fix_notes.append(fix_path.read_text(encoding="utf-8").strip())
        if fix_notes:
            sections.append("### Fix Audit Trail\n")
            sections.append("\n\n---\n\n".join(fix_notes))

    if not sections:
        return ""

    return "## Vault Context (from prior steps and runs)\n\n" + "\n\n".join(sections)


def _load_step_notes_before(run_dir: Path, step_number: int) -> str:
    """Load step notes from a run directory for steps before step_number.

    Args:
        run_dir: Path to the run directory.
        step_number: Only include notes for steps before this number.

    Returns:
        Concatenated note content (truncated to key sections).
    """
    notes: list[str] = []
    for note_path in sorted(run_dir.glob("step-*.md")):
        # Extract step number from filename
        match = re.match(r"step-(\d+)-", note_path.name)
        if match and int(match.group(1)) < step_number:
            content = note_path.read_text(encoding="utf-8")
            # Include everything except the raw agent output sections
            truncated = _truncate_note(content)
            notes.append(truncated)

    return "\n\n---\n\n".join(notes)


def _load_step_notes_summary(run_dir: Path) -> str:
    """Load a summary of all step notes from a prior run.

    More compressed than current-run notes — just APIs and file lists.

    Args:
        run_dir: Path to the run directory.

    Returns:
        Compressed summary of the run's steps.
    """
    summaries: list[str] = []

    # Try run-summary.md first
    summary_path = run_dir / "run-summary.md"
    if summary_path.exists():
        return summary_path.read_text(encoding="utf-8")

    # Fall back to individual step notes
    for note_path in sorted(run_dir.glob("step-*.md")):
        content = note_path.read_text(encoding="utf-8")
        # Extract just header, files, and APIs
        truncated = _truncate_note(content)
        summaries.append(truncated)

    return "\n\n".join(summaries)


def _find_prior_runs(plan_dir: Path, exclude_run_id: str | None = None) -> list[Path]:
    """Find prior run directories, newest first.

    Args:
        plan_dir: Directory for a specific plan slug.
        exclude_run_id: Run ID to exclude (the current run).

    Returns:
        List of run directory Paths, sorted newest first.
    """
    runs = []
    for d in plan_dir.iterdir():
        if d.is_dir() and d.name != exclude_run_id:
            # Check it has at least one step note
            if list(d.glob("step-*.md")):
                runs.append(d)

    return sorted(runs, reverse=True)


def _truncate_note(content: str) -> str:
    """Truncate a step note to key sections only.

    Removes the raw agent output sections to keep context compact.

    Args:
        content: Full step note markdown.

    Returns:
        Truncated content without agent output sections.
    """
    # Remove agent output sections (they're large)
    for section in ("IMPLEMENT Phase Output", r"Fix Iteration \d+"):
        content = re.sub(
            rf"## {section}.*?(?=^## |\Z)",
            "",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
    return content.strip()


def _render_step_note(note: StepNote) -> str:
    """Render a StepNote as markdown.

    Args:
        note: The step note to render.

    Returns:
        Markdown string.
    """
    lines = [
        f"# Step {note.step_number} — {note.title}",
        "",
        f"- **Tests**: {note.test_count} ({'passed' if note.test_passed else 'FAILED'})",
        f"- **Attempts**: {note.attempts}",
        "",
    ]

    if note.files_created:
        lines.extend(["## Files Created/Modified", ""])
        for f in note.files_created:
            lines.append(f"- `{f}`")
        lines.append("")

    if note.test_files:
        lines.extend(["## Test Files", ""])
        for f in note.test_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if note.public_apis:
        lines.extend(["## Public APIs", ""])
        lines.append("```python")
        lines.extend(note.public_apis)
        lines.append("```")
        lines.append("")

    if note.implement_output:
        lines.extend([
            "## IMPLEMENT Phase Output",
            "",
            "<details>",
            "<summary>Agent output (click to expand)</summary>",
            "",
            note.implement_output[:5000],  # Cap at 5k chars
            "",
            "</details>",
            "",
        ])

    if note.fix_outputs:
        for i, fix_output in enumerate(note.fix_outputs, 1):
            lines.extend([
                f"## Fix Iteration {i}",
                "",
                "<details>",
                "<summary>Agent output (click to expand)</summary>",
                "",
                fix_output[:3000],  # Cap at 3k chars per fix
                "",
                "</details>",
                "",
            ])

    if note.verify_failures:
        lines.extend(["## Verify Failures", ""])
        for failure in note.verify_failures[:20]:  # Cap at 20 failures
            lines.append(f"- {failure}")
        lines.append("")

    if note.review_findings:
        lines.extend(["## Review Findings", ""])
        for finding in note.review_findings:
            lines.append(f"- {finding}")
        lines.append("")

    return "\n".join(lines)


def extract_public_apis(files: list[str], cwd: str) -> list[str]:
    """Extract public function and class signatures from source files.

    Uses Python AST to find public functions and classes (not prefixed
    with underscore).

    Args:
        files: List of file paths relative to cwd.
        cwd: Repository root.

    Returns:
        List of signature strings like ``def score_structure(content: str) -> DimensionScore``.
    """
    signatures: list[str] = []
    cwd_path = Path(cwd)

    for file_path in files:
        full_path = cwd_path / file_path
        if not full_path.exists() or not full_path.suffix == ".py":
            continue

        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        rel = file_path
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                sig = _format_func_signature(node)
                signatures.append(f"# {rel}")
                signatures.append(sig)

            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                signatures.append(f"# {rel}")
                signatures.append(f"class {node.name}:")

                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        sig = _format_func_signature(item)
                        signatures.append(f"    {sig}")

    return signatures


def _format_func_signature(node: ast.FunctionDef) -> str:
    """Format a function AST node as a signature string.

    Args:
        node: AST function definition node.

    Returns:
        Signature string like ``def foo(x: int, y: str) -> bool: ...``
    """
    args_parts: list[str] = []

    for arg in node.args.args:
        name = arg.arg
        if name == "self":
            args_parts.append("self")
            continue
        annotation = ""
        if arg.annotation:
            annotation = f": {ast.unparse(arg.annotation)}"
        args_parts.append(f"{name}{annotation}")

    returns = ""
    if node.returns:
        returns = f" -> {ast.unparse(node.returns)}"

    return f"def {node.name}({', '.join(args_parts)}){returns}: ..."

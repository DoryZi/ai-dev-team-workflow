"""Static code checks for the dev-cycle pipeline.

Runs deterministic checks on Python files to catch convention violations
that don't require LLM judgment. Used during the FINAL_REVIEW phase.

Checks:
- File size (max 500 lines)
- Function length (max 50 lines)
- print() in production code
- Missing ``from __future__ import annotations``
- Hardcoded secrets
"""
from __future__ import annotations

import ast
import io
import logging
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Patterns ---

_PRINT_STATEMENT_RE = re.compile(r"^\s*print\s*\(")

_FUTURE_ANNOTATIONS_RE = re.compile(
    r"^\s*from\s+__future__\s+import\s+annotations\b"
)

_HARDCODED_SECRET_PATTERNS = [
    re.compile(r"""=\s*["']sk-[A-Za-z0-9]"""),
    re.compile(r"""\bapi_key\s*=\s*["'][^"']+["']"""),
    re.compile(r"""\bsecret\s*=\s*["'][^"']+["']"""),
    re.compile(r"""\bpassword\s*=\s*["'][^"']+["']""", re.IGNORECASE),
    re.compile(r"""\btoken\s*=\s*["'](?:sk-|ghp_|gho_|xox[bpas]-)[^"']*["']"""),
]

# Files exempt from the print() check
_PRINT_EXEMPT_PREFIXES = ("tests/", "test_", "scripts/")

_PYTHON_EXT = ".py"

# Limits from conventions/python-coding.md
_MAX_FILE_LINES = 500
_MAX_FUNCTION_LINES = 50


@dataclass
class StaticViolation:
    """A single static check violation.

    Attributes:
        file: Relative file path where the violation was found.
        line: Line number of the violation (1-based).
        rule: Short identifier for the violated rule.
        message: Human-readable description of the violation.
    """

    file: str
    line: int
    rule: str
    message: str


def check_files(
    changed_files: list[str], repo_root: str | Path
) -> list[StaticViolation]:
    """Run all static checks on changed Python files.

    Args:
        changed_files: List of file paths relative to repo_root.
        repo_root: Path to the repository root.

    Returns:
        List of violations found across all files.
    """
    repo_root = Path(repo_root)
    violations: list[StaticViolation] = []

    for file_path in changed_files:
        if not file_path.endswith(_PYTHON_EXT):
            continue

        full_path = repo_root / file_path
        if not full_path.is_file():
            logger.warning("File not found, skipping: %s", full_path)
            continue

        try:
            content = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Could not read %s: %s", full_path, e)
            continue

        lines = content.splitlines()
        string_lines = _find_string_lines(content)

        violations.extend(_check_file_size(file_path, lines))
        violations.extend(_check_function_length(file_path, content))
        violations.extend(_check_print_calls(file_path, lines, string_lines))
        violations.extend(_check_future_annotations(file_path, lines, content))
        violations.extend(_check_hardcoded_secrets(file_path, lines, string_lines))

    return violations


def _find_string_lines(content: str) -> set[int]:
    """Find line numbers inside string literals or docstrings.

    Uses Python's tokenizer to identify multi-line string regions.

    Args:
        content: Full file content.

    Returns:
        Set of 1-based line numbers inside string literals.
    """
    string_lines: set[int] = set()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(content).readline))
    except tokenize.TokenError:
        return string_lines

    for tok in tokens:
        if tok.type == tokenize.STRING:
            start_line = tok.start[0]
            end_line = tok.end[0]
            if start_line == end_line:
                continue
            for line_no in range(start_line, end_line + 1):
                string_lines.add(line_no)

    return string_lines


def _is_code_line(line_no: int, lines: list[str], string_lines: set[int]) -> bool:
    """Check if a line is actual code (not string literal or comment).

    Args:
        line_no: 1-based line number.
        lines: File content split into lines.
        string_lines: Set of line numbers inside string literals.

    Returns:
        True if the line should be checked.
    """
    if line_no in string_lines:
        return False
    line = lines[line_no - 1] if line_no <= len(lines) else ""
    if line.strip().startswith("#"):
        return False
    return True


def _is_test_or_script(file_path: str) -> bool:
    """Check if a file is exempt from the print() check.

    Args:
        file_path: Relative file path.

    Returns:
        True if the file is a test or script file.
    """
    normalized = file_path.replace("\\", "/")
    parts = normalized.split("/")
    basename = parts[-1] if parts else normalized

    if any(part == "tests" for part in parts):
        return True
    if basename.startswith("test_"):
        return True
    for prefix in _PRINT_EXEMPT_PREFIXES:
        if normalized.startswith(prefix) or ("/" + prefix) in normalized:
            return True
    return False


def _check_file_size(
    file_path: str, lines: list[str]
) -> list[StaticViolation]:
    """Check if file exceeds the maximum line count.

    Args:
        file_path: Relative file path.
        lines: File content split into lines.

    Returns:
        List with one violation if file is too large.
    """
    if len(lines) > _MAX_FILE_LINES:
        return [
            StaticViolation(
                file=file_path,
                line=len(lines),
                rule="file_size",
                message=f"File has {len(lines)} lines (max {_MAX_FILE_LINES})",
            )
        ]
    return []


def _check_function_length(
    file_path: str, content: str
) -> list[StaticViolation]:
    """Check if any function exceeds the maximum line count.

    Uses AST parsing to find function definitions and their line spans.

    Args:
        file_path: Relative file path.
        content: Full file content.

    Returns:
        List of violations for each oversized function.
    """
    violations: list[StaticViolation] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or start
            length = end - start + 1
            if length > _MAX_FUNCTION_LINES:
                violations.append(
                    StaticViolation(
                        file=file_path,
                        line=start,
                        rule="function_length",
                        message=f"Function '{node.name}' has {length} lines (max {_MAX_FUNCTION_LINES})",
                    )
                )
    return violations


def _check_print_calls(
    file_path: str, lines: list[str], string_lines: set[int]
) -> list[StaticViolation]:
    """Check for print() calls in production code.

    Args:
        file_path: Relative file path.
        lines: File content split into lines.
        string_lines: Set of line numbers inside string literals.

    Returns:
        List of violations for each print statement.
    """
    if _is_test_or_script(file_path):
        return []

    violations: list[StaticViolation] = []
    for i, line in enumerate(lines):
        line_no = i + 1
        if not _is_code_line(line_no, lines, string_lines):
            continue
        if _PRINT_STATEMENT_RE.match(line):
            violations.append(
                StaticViolation(
                    file=file_path,
                    line=line_no,
                    rule="print_call",
                    message=f"print() in production code: {line.strip()[:80]}",
                )
            )
    return violations


def _check_future_annotations(
    file_path: str, lines: list[str], content: str
) -> list[StaticViolation]:
    """Check for missing ``from __future__ import annotations``.

    Args:
        file_path: Relative file path.
        lines: File content split into lines.
        content: Full file content.

    Returns:
        List with one violation if the import is missing.
    """
    if not content.strip():
        return []

    non_empty = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    if not non_empty:
        return []

    if _FUTURE_ANNOTATIONS_RE.search(content):
        return []

    return [
        StaticViolation(
            file=file_path,
            line=1,
            rule="missing_future_annotations",
            message="Missing `from __future__ import annotations`",
        )
    ]


def _check_hardcoded_secrets(
    file_path: str, lines: list[str], string_lines: set[int]
) -> list[StaticViolation]:
    """Check for hardcoded secret patterns.

    Args:
        file_path: Relative file path.
        lines: File content split into lines.
        string_lines: Set of line numbers inside string literals.

    Returns:
        List of violations for each hardcoded secret.
    """
    violations: list[StaticViolation] = []
    for i, line in enumerate(lines):
        line_no = i + 1
        if not _is_code_line(line_no, lines, string_lines):
            continue
        for pattern in _HARDCODED_SECRET_PATTERNS:
            if pattern.search(line):
                violations.append(
                    StaticViolation(
                        file=file_path,
                        line=line_no,
                        rule="hardcoded_secret",
                        message=f"Possible hardcoded secret: {line.strip()[:80]}",
                    )
                )
                break
    return violations

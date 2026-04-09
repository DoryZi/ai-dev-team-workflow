"""AST-based checkers for individual coding convention categories.

Each checker takes Python source code and a Rule, returning a CheckResult
with a score from 0.0 to 1.0 indicating adherence to the convention.
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from evaluator.models import CheckResult

if TYPE_CHECKING:
    from evaluator.rule_parser import Rule

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50
MAX_CLASS_LINES = 300


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_or_fail(source: str) -> ast.Module | None:
    """Try to parse source; return None on SyntaxError.

    Args:
        source: Python source code to parse.

    Returns:
        Parsed AST module, or None if a SyntaxError occurred.
    """
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _syntax_error_result(source: str, rule: Rule) -> CheckResult:
    """Build a failing CheckResult when source cannot be parsed.

    Args:
        source: Python source code that failed to parse.
        rule: Rule being checked.

    Returns:
        CheckResult with score 0.0 and the syntax error details.
    """
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return CheckResult(
            rule_id=rule.id,
            rule_category=rule.category,
            passed=False,
            score=0.0,
            details=f"Syntax error prevents AST parsing: {exc}",
            violations=[str(exc)],
        )
    return CheckResult(  # pragma: no cover
        rule_id=rule.id,
        rule_category=rule.category,
        passed=False,
        score=0.0,
        details="Unknown parse error",
    )


def _node_line_count(node: ast.AST) -> int:
    """Count the number of source lines spanned by an AST node.

    Args:
        node: An AST node with lineno and end_lineno attributes.

    Returns:
        Number of lines the node spans, or 0 if line info is unavailable.
    """
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if start is not None and end is not None:
        return end - start + 1
    return 0


def _make_result(rule: Rule, score: float, details: str, violations: list[str]) -> CheckResult:
    """Create a CheckResult with consistent passed logic.

    Args:
        rule: Rule being checked.
        score: Adherence score 0.0 to 1.0.
        details: Human-readable explanation.
        violations: List of violation descriptions.

    Returns:
        Constructed CheckResult.
    """
    return CheckResult(
        rule_id=rule.id,
        rule_category=rule.category,
        passed=score >= 1.0,
        score=round(score, 4),
        details=details,
        violations=violations,
    )


# ---------------------------------------------------------------------------
# Check: type_hints
# ---------------------------------------------------------------------------


def check_type_hints(source: str, rule: Rule) -> CheckResult:
    """Check that function defs have return and argument type annotations.

    Args:
        source: Python source code to analyse.
        rule: The type_hints rule being checked.

    Returns:
        CheckResult with score = annotated / total annotations expected.
    """
    tree = _parse_or_fail(source)
    if tree is None:
        return _syntax_error_result(source, rule)

    total = 0
    annotated = 0
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_name = node.name

        # Return annotation
        total += 1
        if node.returns is not None:
            annotated += 1
        else:
            violations.append(f"{func_name}() missing return type annotation (line {node.lineno})")

        # Argument annotations (skip 'self' and 'cls')
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            total += 1
            if arg.annotation is not None:
                annotated += 1
            else:
                violations.append(
                    f"{func_name}() arg '{arg.arg}' missing type annotation (line {node.lineno})"
                )

    if total == 0:
        return _make_result(rule, 1.0, "No functions found; nothing to check.", [])

    score = annotated / total
    return _make_result(rule, score, f"{annotated}/{total} annotations present.", violations)


# ---------------------------------------------------------------------------
# Check: docstrings
# ---------------------------------------------------------------------------


def check_docstrings(source: str, rule: Rule) -> CheckResult:
    """Check that all public functions and classes have docstrings.

    Args:
        source: Python source code to analyse.
        rule: The docstrings rule being checked.

    Returns:
        CheckResult with score = documented / total public definitions.
    """
    tree = _parse_or_fail(source)
    if tree is None:
        return _syntax_error_result(source, rule)

    total = 0
    documented = 0
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            total += 1
            if ast.get_docstring(node):
                documented += 1
            else:
                violations.append(
                    f"Function '{node.name}' missing docstring (line {node.lineno})"
                )
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            total += 1
            if ast.get_docstring(node):
                documented += 1
            else:
                violations.append(
                    f"Class '{node.name}' missing docstring (line {node.lineno})"
                )

    if total == 0:
        return _make_result(rule, 1.0, "No public definitions found; nothing to check.", [])

    score = documented / total
    return _make_result(
        rule, score, f"{documented}/{total} public definitions documented.", violations
    )


# ---------------------------------------------------------------------------
# Check: imports
# ---------------------------------------------------------------------------


def _find_wildcard_violations(import_nodes: list[ast.stmt]) -> list[str]:
    """Find wildcard import violations.

    Args:
        import_nodes: List of import AST nodes.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []
    for node in import_nodes:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    violations.append(
                        f"Wildcard import 'from {node.module} import *' (line {node.lineno})"
                    )
    return violations


def _find_multi_import_violations(import_nodes: list[ast.stmt]) -> list[str]:
    """Find multi-import-on-one-line violations.

    Args:
        import_nodes: List of import AST nodes.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []
    for node in import_nodes:
        if isinstance(node, ast.Import) and len(node.names) > 1:
            names = ", ".join(a.name for a in node.names)
            violations.append(
                f"Multi-import on one line: 'import {names}' (line {node.lineno})"
            )
    return violations


def _find_non_top_import_violations(tree: ast.Module) -> list[str]:
    """Find imports that are not at the top of the file.

    Args:
        tree: Parsed AST module.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []
    past_imports = False

    for stmt in tree.body:
        is_import = isinstance(stmt, (ast.Import, ast.ImportFrom))
        is_docstring = isinstance(stmt, ast.Expr) and isinstance(
            stmt.value, (ast.Constant, ast.Str)
        )
        is_dunder_assign = isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id.startswith("__") and t.id.endswith("__")
            for t in stmt.targets
        )
        is_if_name_main = isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Compare)

        if is_import and past_imports:
            violations.append(f"Import not at top of file (line {stmt.lineno})")
        elif not is_import and not is_docstring and not is_dunder_assign and not is_if_name_main:
            past_imports = True

    return violations


def check_imports(source: str, rule: Rule) -> CheckResult:
    """Check import hygiene: top-of-file, no wildcards, no multi-imports.

    Args:
        source: Python source code to analyse.
        rule: The imports rule being checked.

    Returns:
        CheckResult scoring import convention adherence.
    """
    tree = _parse_or_fail(source)
    if tree is None:
        return _syntax_error_result(source, rule)

    import_nodes: list[ast.stmt] = [
        node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    if not import_nodes:
        return _make_result(rule, 1.0, "No imports found; nothing to check.", [])

    violations: list[str] = []
    violations.extend(_find_wildcard_violations(import_nodes))
    violations.extend(_find_multi_import_violations(import_nodes))
    violations.extend(_find_non_top_import_violations(tree))

    total_checks = max(len(import_nodes), 1)
    passed_checks = total_checks - len(violations)
    score = max(0.0, passed_checks / total_checks)

    return _make_result(rule, score, f"{len(violations)} import violation(s) found.", violations)


# ---------------------------------------------------------------------------
# Check: paths
# ---------------------------------------------------------------------------


def check_paths(source: str, rule: Rule) -> CheckResult:
    """Check for os.path usage (violation) vs pathlib (preferred).

    Args:
        source: Python source code to analyse.
        rule: The paths rule being checked.

    Returns:
        CheckResult with score 1.0 if no os.path usage, 0.0 otherwise.
    """
    tree = _parse_or_fail(source)
    if tree is None:
        return _syntax_error_result(source, rule)

    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "os"
            and node.value.attr == "path"
        ):
            violations.append(
                f"os.path.{node.attr} usage (line {node.lineno}) — use pathlib instead"
            )
        elif (
            isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr == "path"
        ):
            violations.append(f"os.path usage (line {node.lineno}) — use pathlib instead")

    score = 0.0 if violations else 1.0
    detail = f"{'No' if not violations else len(violations)} os.path usage(s) found."
    return _make_result(rule, score, detail, violations)


# ---------------------------------------------------------------------------
# Check: error_handling
# ---------------------------------------------------------------------------


def check_error_handling(source: str, rule: Rule) -> CheckResult:
    """Check for bare except clauses and except-pass anti-patterns.

    Args:
        source: Python source code to analyse.
        rule: The error_handling rule being checked.

    Returns:
        CheckResult scoring error handling convention adherence.
    """
    tree = _parse_or_fail(source)
    if tree is None:
        return _syntax_error_result(source, rule)

    violations: list[str] = []
    total_handlers = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        total_handlers += 1
        if node.type is None:
            violations.append(f"Bare 'except:' clause (line {node.lineno})")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            violations.append(f"Silent 'except: pass' clause (line {node.lineno})")

    if total_handlers == 0:
        return _make_result(rule, 1.0, "No exception handlers found; nothing to check.", [])

    clean = total_handlers - min(len(violations), total_handlers)
    score = clean / total_handlers
    detail = f"{len(violations)} error handling violation(s) in {total_handlers} handler(s)."
    return _make_result(rule, score, detail, violations)


# ---------------------------------------------------------------------------
# Check: file_size
# ---------------------------------------------------------------------------


def check_file_size(source: str, rule: Rule) -> CheckResult:
    """Check line counts against per-scope maximums.

    Limits: function max 50 lines, class max 300 lines, file max 500 lines.

    Args:
        source: Python source code to analyse.
        rule: The file_size rule being checked.

    Returns:
        CheckResult scoring compliance with size limits.
    """
    tree = _parse_or_fail(source)
    if tree is None:
        return _syntax_error_result(source, rule)

    violations: list[str] = []
    total_checks = 0
    passed_checks = 0

    file_lines = len(source.splitlines())

    total_checks += 1
    if file_lines <= MAX_FILE_LINES:
        passed_checks += 1
    else:
        violations.append(f"File has {file_lines} lines (max {MAX_FILE_LINES})")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total_checks += 1
            func_lines = _node_line_count(node)
            if func_lines <= MAX_FUNCTION_LINES:
                passed_checks += 1
            else:
                violations.append(
                    f"Function '{node.name}' has {func_lines} lines "
                    f"(max {MAX_FUNCTION_LINES}, line {node.lineno})"
                )
        elif isinstance(node, ast.ClassDef):
            total_checks += 1
            class_lines = _node_line_count(node)
            if class_lines <= MAX_CLASS_LINES:
                passed_checks += 1
            else:
                violations.append(
                    f"Class '{node.name}' has {class_lines} lines "
                    f"(max {MAX_CLASS_LINES}, line {node.lineno})"
                )

    score = passed_checks / total_checks if total_checks > 0 else 1.0
    detail = f"{passed_checks}/{total_checks} size checks passed."
    return _make_result(rule, score, detail, violations)

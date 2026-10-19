# Copyright (C) 2026 FreeCAD Cloth contributors
"""Reject runtime rewriting or generated execution of checked-in Python source."""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_NAME_HINTS = {
    "source",
    "source_text",
    "python_source",
    "source_code",
    "script_source",
}
WRITE_METHODS = {"write_text", "write_bytes"}
READ_METHODS = {"read_text", "read_bytes", "read"}
INLINE_EDIT_COMMANDS = (
    re.compile(r"(?im)\bsed\s+-i(?:\S*)?\b"),
    re.compile(r"(?im)\b(?:perl|ruby)\s+-[^\s]*p[^\s]*i[^\s]*\b"),
)
INLINE_PYTHON_EDIT = re.compile(
    r"(?i)\bpython(?:3(?:\.\d+)?)?\s+-c\b[^\n]*(?:\.replace\s*\(|\.write_text\s*\(|\.write_bytes\s*\()"
)


def _target_names(target: ast.expr) -> set[str]:
    """Return simple variable names assigned by one assignment target.

    Args:
        target: Syntax node representing an assignment target.

    Returns:
        Names of variables bound by the target expression.
    """
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for element in target.elts:
            result.update(_target_names(element))
        return result
    return set()


def _contains_python_path_literal(node: ast.AST) -> bool:
    """Recognize path expressions that explicitly identify a Python source file.

    Args:
        node: Syntax node to inspect for source-path literals.

    Returns:
        Whether the expression refers to a Python source path.
    """
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and (child.value.endswith(".py") or child.value.endswith(".pyi"))
        ):
            return True
        if isinstance(child, ast.Name) and child.id == "__file__":
            return True
    return False


def _read_method_receiver(node: ast.AST) -> ast.expr | None:
    """Return the receiver of a read call, if this node represents file reading.

    Args:
        node: Syntax node being tested as a file-read call.

    Returns:
        Receiver expression for a recognized read call, or None.
    """
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr not in READ_METHODS:
        return None
    return node.func.value


def _names_used(node: ast.AST) -> set[str]:
    """Collect every referenced identifier contained in a syntax node.

    Args:
        node: Syntax subtree whose identifier references should be collected.

    Returns:
        Set of names used by the subtree.
    """
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _checked_in_source_handles(tree: ast.Module, python_path_names: set[str]) -> set[str]:
    """Find file handles opened from known Python paths inside with statements.

    Args:
        tree: Parsed module syntax tree to inspect.
        python_path_names: Identifiers known to refer to Python source paths.

    Returns:
        Names bound to file handles opened from checked-in source paths.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        for item in node.items:
            expression = item.context_expr
            if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
                continue
            if expression.func.id != "open" or not expression.args:
                continue
            source_path = expression.args[0]
            if _names_used(source_path) & python_path_names or _contains_python_path_literal(
                source_path
            ):
                names.update(_target_names(item.optional_vars) if item.optional_vars else set())
    return names


def _is_checked_in_source_expression(
    expression: ast.expr,
    source_names: set[str],
    python_path_names: set[str],
) -> bool:
    """Return whether an expression reads unchanged text from a known Python file.

    Args:
        expression: Expression whose source provenance is being checked.
        source_names: Identifiers known to hold text read from source files.
        python_path_names: Identifiers known to refer to Python source paths.

    Returns:
        Whether the expression can be traced to checked-in Python source.
    """
    if isinstance(expression, ast.Name):
        return expression.id in source_names
    receiver = _read_method_receiver(expression)
    return receiver is not None and bool(
        _names_used(receiver) & (python_path_names | source_names)
        or _contains_python_path_literal(receiver)
    )


def _assignment_targets(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> list[ast.expr]:
    """Return every expression that receives a value from an assignment.

    Args:
        node: Assignment, annotated assignment, or named expression to inspect.

    Returns:
        Assignment target expressions in source order.
    """
    if isinstance(node, ast.Assign):
        return node.targets
    return [node.target]


def _assignment_names(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> set[str]:
    """Collect simple names bound by an assignment statement.

    Args:
        node: Assignment expression whose targets should be examined.

    Returns:
        Names bound directly or through tuple/list unpacking.
    """
    names: set[str] = set()
    for target in _assignment_targets(node):
        names.update(_target_names(target))
    return names


def _seed_python_path_names(assignments: list[ast.Assign | ast.AnnAssign | ast.NamedExpr]) -> set[str]:
    """Find assignments whose values identify a Python source path.

    Args:
        assignments: Assignment nodes gathered from the parsed module.

    Returns:
        Names assigned expressions that explicitly reference Python source paths.
    """
    names: set[str] = set()
    for node in assignments:
        if node.value is not None and _contains_python_path_literal(node.value):
            names.update(_assignment_names(node))
    return names


def _looks_like_source_read(
    node: ast.Assign | ast.AnnAssign | ast.NamedExpr,
    python_path_names: set[str],
) -> bool:
    """Determine whether an assignment reads text from a Python source path.

    Args:
        node: Assignment whose value may read checked-in source text.
        python_path_names: Names already known to refer to Python source paths.

    Returns:
        Whether the assignment appears to capture source text.
    """
    if node.value is None:
        return False
    receiver = _read_method_receiver(node.value)
    if receiver is None:
        return False
    receiver_names = _names_used(receiver)
    if receiver_names & python_path_names:
        return True
    if _contains_python_path_literal(receiver):
        return True
    return bool(_assignment_names(node) & PYTHON_SOURCE_NAME_HINTS)


def _call_rewrites_known_source(node: ast.Call, source_names: set[str]) -> bool:
    """Return whether a call rewrites or substitutes known Python source text.

    Args:
        node: Call expression being classified.
        source_names: Names known to hold checked-in Python source contents.

    Returns:
        Whether the call modifies source text through replace or regex substitution.
    """
    if isinstance(node.func, ast.Attribute):
        if node.func.attr == "replace":
            return bool(_names_used(node.func.value) & source_names)
        if node.func.attr in {"sub", "subn"}:
            return any(_names_used(argument) & source_names for argument in node.args)
    if isinstance(node.func, ast.Name) and node.func.id in {"sub", "subn"}:
        return any(_names_used(argument) & source_names for argument in node.args)
    return False


def _propagate_assignment_names(
    node: ast.Assign | ast.AnnAssign | ast.NamedExpr,
    python_path_names: set[str],
    source_names: set[str],
    modified_source_names: set[str],
) -> bool:
    """Propagate source-reading and source-modification names through an assignment.

    Args:
        node: Assignment node being analyzed.
        python_path_names: Names known to refer to Python source paths.
        source_names: Mutable set of names that may contain checked-in source.
        modified_source_names: Mutable set of names holding transformed source text.

    Returns:
        Whether either tracked set gained a newly identified name.
    """
    changed = False
    value = node.value
    if value is None:
        return False

    if _looks_like_source_read(node, python_path_names):
        before = len(source_names)
        source_names.update(_assignment_names(node))
        changed = len(source_names) != before

    transformed = isinstance(value, ast.Call) and _call_rewrites_known_source(value, source_names)
    derived = isinstance(value, ast.BinOp) and bool(
        _names_used(value) & (source_names | modified_source_names)
    )
    if transformed or derived:
        before = len(modified_source_names)
        modified_source_names.update(_assignment_names(node))
        changed = changed or len(modified_source_names) != before
    return changed


def _resolve_source_names(
    assignments: list[ast.Assign | ast.AnnAssign | ast.NamedExpr],
    python_path_names: set[str],
    source_names: set[str],
    modified_source_names: set[str],
) -> None:
    """Resolve aliases of source text and its transformed variants to a fixed point.

    Args:
        assignments: Assignment nodes from the source module.
        python_path_names: Names known to refer to Python source paths.
        source_names: Mutable set of names holding checked-in source text.
        modified_source_names: Mutable set of names holding modified source text.
    """
    for _ in range(4):
        changed = False
        for node in assignments:
            changed = (
                _propagate_assignment_names(
                    node,
                    python_path_names,
                    source_names,
                    modified_source_names,
                )
                or changed
            )
        if not changed:
            return


@dataclass(slots=True)
class _SourceAnalysis:
    """Collect names and diagnostics while auditing one parsed Python module.

    Attributes:
        path: Relative filename used in policy diagnostics.
        python_path_names: Names known to reference Python source paths.
        source_names: Names known to hold unchanged checked-in source text.
        modified_source_names: Names known to hold transformed source text.
        violations: Mutable policy diagnostics accumulated by analysis helpers.
    """

    path: str
    python_path_names: set[str]
    source_names: set[str]
    modified_source_names: set[str]
    violations: list[str]


def _record_exec_compile_violation(expression: ast.expr, analysis: _SourceAnalysis) -> None:
    """Record a generated-code violation for a compile call nested in exec.

    Args:
        expression: First argument passed to the nested compile call.
        analysis: Module analysis state with known source aliases and diagnostics.
    """
    generated_name = isinstance(expression, ast.Name) and expression.id not in analysis.source_names
    literal_expression = isinstance(expression, (ast.Constant, ast.BinOp, ast.JoinedStr))
    generated_expression = literal_expression and not (
        _names_used(expression) & analysis.source_names
    )
    if generated_name or generated_expression:
        analysis.violations.append(
            f"{analysis.path}:{expression.lineno}: generated Python source must not be executed"
        )


def _record_exec_call_violation(node: ast.Call, analysis: _SourceAnalysis) -> None:
    """Reject dynamic execution of generated or transformed Python source.

    Args:
        node: Call expression being examined.
        analysis: Module analysis state with source aliases and diagnostics.
    """
    if not isinstance(node.func, ast.Name) or node.func.id != "exec" or not node.args:
        return
    expression = node.args[0]
    if _names_used(expression) & analysis.modified_source_names:
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: transformed source must not be executed dynamically"
        )
        return
    if isinstance(expression, ast.Call):
        if (
            isinstance(expression.func, ast.Name)
            and expression.func.id == "compile"
            and expression.args
        ):
            _record_exec_compile_violation(expression.args[0], analysis)
        return
    generated_literal = isinstance(expression, (ast.Constant, ast.BinOp, ast.JoinedStr))
    if generated_literal and not (_names_used(expression) & analysis.source_names):
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: generated Python source must not be executed"
        )
    elif isinstance(expression, ast.Name) and expression.id not in analysis.source_names:
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: generated Python source must not be executed"
        )


def _record_source_mutation_violation(node: ast.Call, analysis: _SourceAnalysis) -> None:
    """Report replacements or file writes that operate on checked-in source text.

    Args:
        node: Call expression being examined.
        analysis: Module analysis state with source aliases and diagnostics.
    """
    if _call_rewrites_known_source(node, analysis.source_names):
        call_name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: Python source text must not be rewritten with "
            f"{call_name}(); use explicit functions/configuration"
        )
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in WRITE_METHODS:
        return
    tracked_names = analysis.source_names | analysis.modified_source_names
    if _names_used(node) & tracked_names:
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: Python source text must not be written after "
            "runtime transformation"
        )


def _record_compile_call_violation(node: ast.Call, analysis: _SourceAnalysis) -> None:
    """Reject compiling generated Python text or text derived by modification.

    Args:
        node: Call expression being examined.
        analysis: Module analysis state with source aliases and diagnostics.
    """
    if not isinstance(node.func, ast.Name) or node.func.id != "compile" or not node.args:
        return
    expression = node.args[0]
    transformed = bool(_names_used(expression) & analysis.modified_source_names)
    derived_expression = isinstance(expression, ast.BinOp) and bool(
        _names_used(expression) & analysis.source_names
    )
    if transformed or derived_expression:
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: transformed source must not be compiled at runtime"
        )
        return
    if not _is_checked_in_source_expression(
        expression,
        analysis.source_names,
        analysis.python_path_names,
    ):
        analysis.violations.append(
            f"{analysis.path}:{node.lineno}: compiling generated Python source is prohibited"
        )


def _record_call_violations(node: ast.Call, analysis: _SourceAnalysis) -> None:
    """Apply all dynamic-execution and source-mutation rules to one call.

    Args:
        node: Call expression being examined.
        analysis: Module analysis state with source aliases and diagnostics.
    """
    _record_exec_call_violation(node, analysis)
    _record_source_mutation_violation(node, analysis)
    _record_compile_call_violation(node, analysis)


def python_source_rewrite_violations(source_text: str, path: str = "<source>") -> tuple[str, ...]:
    """Find Python-source replacement, file-write, and dynamic execution patterns.

    Args:
        source_text: Python source code to inspect.
        path: Filename used to label any diagnostic.

    Returns:
        Source-rewriting policy violations found in the module.
    """
    try:
        tree = ast.parse(source_text, filename=path)
    except SyntaxError as error:
        return (f"{path}:{error.lineno or 1}: invalid Python syntax: {error.msg}",)

    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
    ]
    python_path_names = _seed_python_path_names(assignments)
    source_names = _checked_in_source_handles(tree, python_path_names)
    modified_source_names: set[str] = set()
    _resolve_source_names(assignments, python_path_names, source_names, modified_source_names)
    analysis = _SourceAnalysis(
        path,
        python_path_names,
        source_names,
        modified_source_names,
        [],
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            _record_call_violations(node, analysis)
    return tuple(sorted(set(analysis.violations)))


def workflow_source_rewrite_violations(text: str, path: str = "<workflow>") -> tuple[str, ...]:
    """Reject inline shell commands that rewrite tracked source/configuration files.

    Args:
        text: Workflow or shell text to inspect.
        path: Filename used to label any diagnostic.

    Returns:
        Source-rewriting violations detected in the workflow text.
    """
    violations: list[str] = []
    for pattern in INLINE_EDIT_COMMANDS:
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            violations.append(
                f"{path}:{line}: inline in-place editing is prohibited; make a reviewed commit"
            )
    for match in INLINE_PYTHON_EDIT.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        violations.append(
            f"{path}:{line}: inline Python source/config rewriting is prohibited; "
            "use reviewed repository changes"
        )
    return tuple(sorted(set(violations)))


def _policy_files() -> tuple[Path, ...]:
    """Return repository Python sources and executable CI configuration files.

    Returns:
        Sorted paths covered by the source-rewriting policy.
    """
    python_files = [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in {".git", ".venv", "__pycache__", "build", "dist"} for part in path.parts)
    ]
    ci_files = list((ROOT / ".github").rglob("*.yml"))
    ci_files.extend((ROOT / ".github").rglob("*.yaml"))
    ci_files.extend((ROOT / "tools").rglob("*.sh"))
    ci_files.extend((ROOT / ".github").rglob("*.sh"))
    return tuple(sorted({*python_files, *ci_files}))


def main() -> int:
    """Scan the repository and fail closed on forbidden source manipulation.

    Returns:
        Process status indicating whether the source-rewriting policy passed.
    """
    errors: list[str] = []
    for path in _policy_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            errors.extend(python_source_rewrite_violations(text, relative))
        elif path.suffix in {".yml", ".yaml", ".sh"}:
            errors.extend(workflow_source_rewrite_violations(text, relative))
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
        return 1
    sys.stdout.write("source-rewriting-policy=passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

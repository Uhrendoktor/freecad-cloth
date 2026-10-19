# Copyright (C) 2026 FreeCAD Cloth contributors
"""Reject explicit ``Any`` references in repository Python sources.

Ruff ANN401 handles function annotations. This syntax-aware gate catches explicit
``Any`` references in aliases and attributes, including quoted forward references
and legacy type comments, which ordinary AST name traversal cannot see.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parents[2]
_TYPE_MODULES = frozenset({"typing", "typing_extensions"})
_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)


def _is_imported_any_name(node: ast.AST, any_names: set[str]) -> bool:
    """Return whether a name node resolves to an imported Any symbol.

    Args:
        node: AST expression to inspect.
        any_names: Local aliases that resolve to typing.Any.

    Returns:
        Whether the expression is a prohibited imported Any reference.
    """
    return isinstance(node, ast.Name) and node.id in any_names


def _is_typing_any_attribute(node: ast.AST, typing_modules: set[str]) -> bool:
    """Return whether an attribute node resolves to typing.Any.

    Args:
        node: AST expression to inspect.
        typing_modules: Local aliases for typing modules.

    Returns:
        Whether the expression accesses Any on an imported typing module.
    """
    if not isinstance(node, ast.Attribute) or node.attr != "Any":
        return False
    return isinstance(node.value, ast.Name) and node.value.id in typing_modules


def _is_any_reference(
    node: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
) -> bool:
    """Identify imported Any names and qualified typing.Any expressions.

    Args:
        node: AST expression to inspect.
        any_names: Local aliases that resolve to typing.Any.
        typing_modules: Local aliases for typing modules.

    Returns:
        Whether the node names the prohibited Any type.
    """
    return _is_imported_any_name(node, any_names) or _is_typing_any_attribute(node, typing_modules)


def _contains_explicit_any(
    node: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
) -> bool:
    """Return whether type syntax references an imported Any name or typing.Any.

    Args:
        node: AST subtree representing annotation syntax to inspect.
        any_names: Imported names that refer to an explicit Any symbol.
        typing_modules: Aliases bound to typing or typing_extensions modules.

    Returns:
        Whether the subtree contains an explicit Any reference.
    """
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, ast.Constant) and isinstance(current.value, str):
            try:
                nested = ast.parse(current.value, mode="eval").body
            except SyntaxError:
                nested = None
            if nested is not None:
                pending.append(nested)
        elif _is_any_reference(current, any_names, typing_modules):
            return True
        pending.extend(ast.iter_child_nodes(current))
    return False


def _type_comment_roots(comment: str) -> tuple[ast.AST, ...]:
    """Parse an assignment type comment or a legacy function-signature comment.

    Args:
        comment: Type comment text attached to an assignment or function.

    Returns:
        Parsed syntax roots for supported comment expressions, or an empty tuple.
    """
    try:
        return (ast.parse(comment, mode="eval").body,)
    except SyntaxError:
        pass

    if "->" not in comment:
        return ()

    arguments, result = comment.rsplit("->", maxsplit=1)
    arguments = arguments.strip()
    if arguments.startswith("(") and arguments.endswith(")"):
        arguments = arguments[1:-1].strip()

    roots: list[ast.AST] = []
    for expression in (arguments, result.strip()):
        if not expression:
            continue
        try:
            roots.append(ast.parse(expression, mode="eval").body)
        except SyntaxError:
            continue
    return tuple(roots)


def _imported_type_symbols(
    tree: ast.AST,
    filename: str,
) -> tuple[set[str], set[str], list[str]]:
    """Collect imported Any aliases, typing module aliases, and wildcard violations.

    Args:
        tree: Parsed source module to inspect.
        filename: Source filename used to label policy diagnostics.

    Returns:
        Any aliases, typing-module aliases, and wildcard-import violations.
    """
    any_names: set[str] = set()
    typing_modules: set[str] = set()
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _TYPE_MODULES:
                    typing_modules.add(alias.asname or alias.name)
            continue
        if not isinstance(node, ast.ImportFrom) or node.module not in _TYPE_MODULES:
            continue
        for alias in node.names:
            if alias.name == "Any":
                any_names.add(alias.asname or alias.name)
            elif alias.name == "*":
                violations.append(
                    f"{filename}:{node.lineno}: wildcard import from {node.module} "
                    "is prohibited by the explicit-Any policy"
                )
    return any_names, typing_modules, violations


def _direct_any_reference_violations(
    tree: ast.AST,
    filename: str,
    any_names: set[str],
    typing_modules: set[str],
) -> list[str]:
    """Find ordinary names and qualified attributes that refer to explicit Any.

    Args:
        tree: Parsed source module to inspect.
        filename: Source filename used to label policy diagnostics.
        any_names: Imported names that refer to explicit Any.
        typing_modules: Aliases bound to typing modules.

    Returns:
        Diagnostics for direct explicit Any references.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if _is_imported_any_name(node, any_names):
            violations.append(
                f"{filename}:{node.lineno}: explicit Any reference is prohibited; "
                "use a concrete type, object with narrowing, or a Protocol"
            )
        elif _is_typing_any_attribute(node, typing_modules):
            module_name = (
                node.value.id
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                else "typing"
            )
            violations.append(
                f"{filename}:{node.lineno}: explicit {module_name}.Any reference is prohibited; "
                "use a concrete type, object with narrowing, or a Protocol"
            )
    return violations


def _stringified_annotation_violations(
    node: ast.AST,
    filename: str,
    any_names: set[str],
    typing_modules: set[str],
) -> list[str]:
    """Report prohibited Any references in a node's stringified annotation.

    Args:
        node: Syntax node whose annotation may be a quoted forward reference.
        filename: Source path used to label policy diagnostics.
        any_names: Imported aliases that resolve to typing.Any.
        typing_modules: Imported aliases used to qualify typing.Any.

    Returns:
        Diagnostics for prohibited stringified annotation references.
    """
    annotation: ast.expr | None = None
    if isinstance(node, ast.arg):
        annotation = node.annotation
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        annotation = node.returns
    elif isinstance(node, ast.AnnAssign):
        annotation = node.annotation

    if not isinstance(annotation, ast.Constant) or not isinstance(annotation.value, str):
        return []
    if not _contains_explicit_any(annotation, any_names, typing_modules):
        return []

    line = getattr(annotation, "lineno", node.lineno)
    return [
        f"{filename}:{line}: stringified annotation references explicit Any; "
        "use a concrete type, object with narrowing, or a Protocol"
    ]


def _type_comment_any_violations(
    node: ast.AST,
    filename: str,
    any_names: set[str],
    typing_modules: set[str],
) -> list[str]:
    """Report prohibited Any references in a node's legacy type comment.

    Args:
        node: Syntax node that may contain a type comment.
        filename: Source path used to label policy diagnostics.
        any_names: Imported aliases that resolve to typing.Any.
        typing_modules: Imported aliases used to qualify typing.Any.

    Returns:
        Diagnostics for prohibited type-comment references.
    """
    type_comment = getattr(node, "type_comment", None)
    if not isinstance(type_comment, str):
        return []
    roots = _type_comment_roots(type_comment)
    if not any(_contains_explicit_any(root, any_names, typing_modules) for root in roots):
        return []

    line = getattr(node, "lineno", 1)
    return [
        f"{filename}:{line}: type comment references explicit Any; "
        "use a concrete type, object with narrowing, or a Protocol"
    ]


def _annotation_any_violations(
    tree: ast.AST,
    filename: str,
    any_names: set[str],
    typing_modules: set[str],
) -> list[str]:
    """Check annotation fields and type comments for stringified explicit Any types.

    Args:
        tree: Parsed source module to inspect.
        filename: Source filename used to label policy diagnostics.
        any_names: Imported names that refer to explicit Any.
        typing_modules: Aliases bound to explicit typing modules.

    Returns:
        Diagnostics for stringified annotations and legacy type comments.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        violations.extend(
            _stringified_annotation_violations(node, filename, any_names, typing_modules)
        )
        violations.extend(_type_comment_any_violations(node, filename, any_names, typing_modules))
    return violations


def explicit_any_violations(source: str, filename: str = "<memory>") -> tuple[str, ...]:
    """Return source locations that explicitly reference typing.Any.

    Imports from typing or typing_extensions are resolved so renamed imports
    cannot bypass the rule. Wildcard imports are rejected because they expose
    Any without an explicit symbol reference. Quoted forward annotations and
    type comments are parsed only in annotation-related fields; ordinary
    user-facing strings are not interpreted as type syntax.

    Args:
        source: Python source text to inspect for explicit Any references.
        filename: Filename included in parse diagnostics and policy violations.

    Returns:
        Sorted, unique diagnostics for syntax errors or prohibited Any references.
    """
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return (f"{filename}:{line}: invalid Python syntax: {exc.msg}",)

    any_names, typing_modules, violations = _imported_type_symbols(tree, filename)
    violations.extend(_direct_any_reference_violations(tree, filename, any_names, typing_modules))
    violations.extend(_annotation_any_violations(tree, filename, any_names, typing_modules))
    return tuple(sorted(set(violations)))


def python_files(root: Path = ROOT) -> Iterator[Path]:
    """Yield Python source files in deterministic order, excluding generated trees.

    Args:
        root: Directory tree to scan for Python source files.

    Yields:
        Python source paths in stable order, excluding generated directories.
    """
    for directory, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in _IGNORED_DIRECTORIES)
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(directory) / name


def main() -> int:
    """Check every repository Python source and fail with actionable locations.

    Returns:
        Process status indicating whether the explicit-Any policy is satisfied.
    """
    violations: list[str] = []
    count = 0
    for path in python_files():
        count += 1
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            relative = path.relative_to(ROOT)
            violations.append(f"{relative}: unable to read Python source: {exc}")
            continue
        violations.extend(explicit_any_violations(source, path.relative_to(ROOT).as_posix()))

    if violations:
        sys.stderr.write("explicit-any-policy=failed\n")
        sys.stderr.write("\n".join(sorted(violations)) + "\n")
        return 1

    sys.stdout.write(f"explicit-any-policy=passed python_files={count}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

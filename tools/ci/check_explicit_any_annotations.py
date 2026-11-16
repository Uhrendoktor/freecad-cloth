# Copyright (C) 2026 FreeCAD Cloth contributors
"""Reject explicit ``Any`` references in repository Python sources and stubs.

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


def _contains_explicit_any(
    node: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
) -> bool:
    """Return whether type syntax references an imported Any name or typing.Any."""
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
        elif (isinstance(current, ast.Name) and current.id in any_names) or (
            isinstance(current, ast.Attribute)
            and current.attr == "Any"
            and isinstance(current.value, ast.Name)
            and current.value.id in typing_modules
        ):
            return True
        pending.extend(ast.iter_child_nodes(current))
    return False


def _type_comment_roots(comment: str) -> tuple[ast.AST, ...]:
    """Parse an assignment type comment or a legacy function-signature comment."""
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


def _imported_any_names(
    tree: ast.Module,
    filename: str,
) -> tuple[set[str], set[str], tuple[str, ...]]:
    """Collect aliases for Any imports and diagnostics for wildcard typing imports.

    Args:
        tree: Parsed module whose imports define the available typing aliases.
        filename: Source label included in wildcard-import diagnostics.

    Returns:
        Imported Any names, typing-module aliases, and wildcard-import diagnostics.
    """
    any_names: set[str] = set()
    typing_modules: set[str] = set()
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            typing_modules.update(
                alias.asname or alias.name for alias in node.names if alias.name in _TYPE_MODULES
            )
        elif isinstance(node, ast.ImportFrom) and node.module in _TYPE_MODULES:
            for alias in node.names:
                if alias.name == "Any":
                    any_names.add(alias.asname or alias.name)
                elif alias.name == "*":
                    violations.append(
                        f"{filename}:{node.lineno}: wildcard import from {node.module} "
                        "is prohibited by the explicit-Any policy"
                    )
    return any_names, typing_modules, tuple(violations)


def _direct_any_reference_violation(
    node: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
    filename: str,
) -> str | None:
    """Describe a direct imported Any or qualified typing.Any reference.

    Args:
        node: AST node inspected for an unrestricted Any reference.
        any_names: Imported aliases for Any.
        typing_modules: Imported aliases for typing and typing_extensions.
        filename: Source label included in the diagnostic.

    Returns:
        A diagnostic for a direct Any reference, or None when the node is unrelated.
    """
    if isinstance(node, ast.Name) and node.id in any_names:
        return (
            f"{filename}:{node.lineno}: explicit Any reference is prohibited; "
            "use a concrete type, Protocol, TypedDict, or recursive JSON value type"
        )
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "Any"
        and isinstance(node.value, ast.Name)
        and node.value.id in typing_modules
    ):
        return (
            f"{filename}:{node.lineno}: explicit {node.value.id}.Any reference is prohibited; "
            "use a concrete type, Protocol, TypedDict, or recursive JSON value type"
        )
    return None


def _annotation_fields(node: ast.AST) -> tuple[ast.AST, ...]:
    """Return annotation expressions attached to one AST declaration.

    Args:
        node: AST node whose runtime annotation fields are inspected.

    Returns:
        Argument, function-result, or annotated-assignment type expressions.
    """
    if isinstance(node, ast.arg) and node.annotation is not None:
        return (node.annotation,)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
        return (node.returns,)
    if isinstance(node, ast.AnnAssign):
        return (node.annotation,)
    return ()


def _stringified_annotation_violation(
    annotation: ast.AST,
    node_line: int,
    any_names: set[str],
    typing_modules: set[str],
    filename: str,
) -> str | None:
    """Describe a quoted forward annotation that contains an explicit Any.

    Args:
        annotation: Annotation expression inspected for a stringified reference.
        node_line: Fallback source line for AST expressions without line metadata.
        any_names: Imported aliases for Any.
        typing_modules: Imported aliases for typing and typing_extensions.
        filename: Source label included in the diagnostic.

    Returns:
        A diagnostic for an offending string annotation, or None when it is valid.
    """
    if (
        isinstance(annotation, ast.Constant)
        and isinstance(annotation.value, str)
        and _contains_explicit_any(annotation, any_names, typing_modules)
    ):
        line = getattr(annotation, "lineno", node_line)
        return (
            f"{filename}:{line}: stringified annotation references explicit Any; "
            "use a concrete type, object with narrowing, or a Protocol"
        )
    return None


def _type_comment_violation(
    node: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
    filename: str,
) -> str | None:
    """Describe a legacy type comment that contains an explicit Any reference.

    Args:
        node: AST node carrying an optional type-comment field.
        any_names: Imported aliases for Any.
        typing_modules: Imported aliases for typing and typing_extensions.
        filename: Source label included in the diagnostic.

    Returns:
        A diagnostic for an offending type comment, or None when it is valid.
    """
    type_comment = getattr(node, "type_comment", None)
    if not isinstance(type_comment, str):
        return None
    roots = _type_comment_roots(type_comment)
    if any(_contains_explicit_any(root, any_names, typing_modules) for root in roots):
        return (
            f"{filename}:{getattr(node, 'lineno', 1)}: type comment references explicit Any; "
            "use a concrete type, Protocol, TypedDict, or recursive JSON value type"
        )
    return None


def explicit_any_violations(source: str, filename: str = "<memory>") -> tuple[str, ...]:
    """Return source locations that explicitly reference typing.Any.

    Args:
        source: Complete Python source or declaration-stub text.
        filename: Source label shown in returned diagnostics.

    Returns:
        Sorted diagnostics for direct, quoted, and legacy type-comment Any references.
    """
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return (f"{filename}:{line}: invalid Python syntax: {exc.msg}",)

    any_names, typing_modules, imported_violations = _imported_any_names(tree, filename)
    violations = list(imported_violations)
    for node in ast.walk(tree):
        direct_violation = _direct_any_reference_violation(
            node,
            any_names,
            typing_modules,
            filename,
        )
        if direct_violation is not None:
            violations.append(direct_violation)
        violations.extend(
            violation
            for annotation in _annotation_fields(node)
            if (
                violation := _stringified_annotation_violation(
                    annotation,
                    getattr(node, "lineno", 1),
                    any_names,
                    typing_modules,
                    filename,
                )
            )
            is not None
        )
        comment_violation = _type_comment_violation(
            node,
            any_names,
            typing_modules,
            filename,
        )
        if comment_violation is not None:
            violations.append(comment_violation)

    return tuple(sorted(set(violations)))


def python_files(root: Path = ROOT) -> Iterator[Path]:
    """Yield Python source files in deterministic order, excluding generated trees.

    Args:
        root: Directory recursively searched for implementation modules and stubs.

    Yields:
        Python source and stub paths in deterministic lexical order.
    """
    for directory, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in _IGNORED_DIRECTORIES)
        for name in sorted(files):
            if name.endswith((".py", ".pyi")):
                yield Path(directory) / name


def main() -> int:
    """Check every repository Python source and fail with actionable locations.

    Returns:
        Zero when every tracked Python source satisfies the explicit-Any policy.
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
        print("explicit-any-policy=failed", file=sys.stderr)
        print("\n".join(sorted(violations)), file=sys.stderr)
        return 1

    print(f"explicit-any-policy=passed python_files={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

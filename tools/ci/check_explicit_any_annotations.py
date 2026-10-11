"""Reject explicit ``Any`` references in repository Python sources.

Ruff ANN401 handles function annotations. This syntax-aware gate catches explicit
``Any`` references in aliases and attributes, including quoted forward references
and legacy type comments, which ordinary AST name traversal cannot see.
"""

from __future__ import annotations

import ast
import os
import sys
from collections.abc import Iterator
from pathlib import Path

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
        elif isinstance(current, ast.Name) and current.id in any_names:
            return True
        elif (
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


def explicit_any_violations(source: str, filename: str = "<memory>") -> tuple[str, ...]:
    """Return source locations that explicitly reference ``typing.Any``.

    Imports from ``typing`` or ``typing_extensions`` are resolved so renamed
    imports cannot bypass the rule. Wildcard imports are rejected because they
    expose ``Any`` without an explicit symbol reference. Quoted forward
    annotations and type comments are parsed only in annotation-related fields;
    ordinary user-facing strings are not interpreted as type syntax.
    """
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return (f"{filename}:{line}: invalid Python syntax: {exc.msg}",)

    any_names: set[str] = set()
    typing_modules: set[str] = set()
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _TYPE_MODULES:
                    typing_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in _TYPE_MODULES:
            for alias in node.names:
                if alias.name == "Any":
                    any_names.add(alias.asname or alias.name)
                elif alias.name == "*":
                    violations.append(
                        f"{filename}:{node.lineno}: wildcard import from {node.module} "
                        "is prohibited by the explicit-Any policy"
                    )

    # Existing syntax references (e.g. Any, alias names, and typing.Any) remain
    # covered across the file. A Constant string is inspected only when it is
    # attached to a real annotation or type-comment field.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in any_names:
            violations.append(
                f"{filename}:{node.lineno}: explicit Any reference is prohibited; "
                "use a concrete type, object with narrowing, or a Protocol"
            )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "Any"
            and isinstance(node.value, ast.Name)
            and node.value.id in typing_modules
        ):
            violations.append(
                f"{filename}:{node.lineno}: explicit {node.value.id}.Any reference is prohibited; "
                "use a concrete type, object with narrowing, or a Protocol"
            )

        annotation_fields: list[ast.AST] = []
        if isinstance(node, ast.arg) and node.annotation is not None:
            annotation_fields.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                annotation_fields.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotation_fields.append(node.annotation)

        for annotation in annotation_fields:
            if (
                isinstance(annotation, ast.Constant)
                and isinstance(annotation.value, str)
                and _contains_explicit_any(annotation, any_names, typing_modules)
            ):
                violations.append(
                    f"{filename}:{getattr(annotation, 'lineno', node.lineno)}: "
                    "stringified annotation references explicit Any; use a concrete type, "
                    "object with narrowing, or a Protocol"
                )

        type_comment = getattr(node, "type_comment", None)
        if isinstance(type_comment, str):
            roots = _type_comment_roots(type_comment)
            if any(
                _contains_explicit_any(root, any_names, typing_modules)
                for root in roots
            ):
                violations.append(
                    f"{filename}:{getattr(node, 'lineno', 1)}: type comment references explicit Any; "
                    "use a concrete type, object with narrowing, or a Protocol"
                )

    return tuple(sorted(set(violations)))


def python_files(root: Path = ROOT) -> Iterator[Path]:
    """Yield Python source files in deterministic order, excluding generated trees."""
    for directory, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in _IGNORED_DIRECTORIES)
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(directory) / name


def main() -> int:
    """Check every repository Python source and fail with actionable locations."""
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

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Enforce repository-wide AST contracts for explicit Any and host imports.

Ruff ANN401 handles function annotations. This syntax-aware gate catches explicit
Any references in aliases, attributes, quoted forward references, and legacy
type comments. It also rejects importlib indirection for literal FreeCAD host
module names while preserving genuinely dynamic module loading.
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
_LITERAL_HOST_MODULE_NAMES = frozenset({"FreeCAD", "FreeCADGui"})
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


def _importlib_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Collect aliases bound to importlib and importlib.import_module.

    Args:
        tree: Parsed Python module.

    Returns:
        Module aliases and function aliases used for importlib calls.
    """
    module_aliases: set[str] = set()
    function_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "importlib"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            function_aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "import_module"
            )
    return module_aliases, function_aliases


def _is_importlib_call(
    node: ast.Call,
    module_aliases: set[str],
    function_aliases: set[str],
) -> bool:
    """Return whether a call resolves to an imported importlib loader.

    Args:
        node: Call expression to inspect.
        module_aliases: Aliases for the importlib module.
        function_aliases: Aliases for importlib.import_module.

    Returns:
        Whether the call target is one of the recorded importlib loaders.
    """
    target = node.func
    if isinstance(target, ast.Name):
        return target.id in function_aliases
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "import_module"
        and isinstance(target.value, ast.Name)
        and target.value.id in module_aliases
    )


def _literal_host_module_name(
    node: ast.Call,
    module_aliases: set[str],
    function_aliases: set[str],
) -> str | None:
    """Return a fixed FreeCAD host-module name loaded by importlib, if any.

    Args:
        node: Call expression to inspect.
        module_aliases: Aliases for the importlib module.
        function_aliases: Aliases for importlib.import_module.

    Returns:
        The prohibited literal host-module name, or None for all other calls.
    """
    if not node.args or not _is_importlib_call(node, module_aliases, function_aliases):
        return None
    argument = node.args[0]
    if (
        isinstance(argument, ast.Constant)
        and isinstance(argument.value, str)
        and argument.value in _LITERAL_HOST_MODULE_NAMES
    ):
        return argument.value
    return None


def literal_host_importlib_violations(
    source: str,
    filename: str = "<memory>",
) -> tuple[str, ...]:
    """Reject importlib indirection for fixed FreeCAD host-module names.

    Importing FreeCAD lazily is valid at a host boundary, but a literal module
    name does not require importlib. A local import or an injected module keeps
    the dependency boundary explicit without evading import-placement lint.

    Args:
        source: Python source text to inspect.
        filename: Filename included in policy diagnostics.

    Returns:
        Sorted diagnostics for constant-name FreeCAD or FreeCADGui imports.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return (f"{filename}:{line}: invalid Python syntax: {exc.msg}",)

    module_aliases, function_aliases = _importlib_aliases(tree)
    violations = [
        (
            f"{filename}:{node.lineno}: importlib is used with the fixed host module "
            f"{module_name!r}; use a direct import at the host boundary or inject "
            "the module dependency"
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for module_name in (_literal_host_module_name(node, module_aliases, function_aliases),)
        if module_name is not None
    ]
    return tuple(sorted(set(violations)))


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


def _typing_import_symbols(
    tree: ast.AST,
    filename: str,
) -> tuple[set[str], set[str], list[str]]:
    """Collect local aliases for typing.Any and typing modules.

    Args:
        tree: Parsed Python module.
        filename: Source path for wildcard-import diagnostics.

    Returns:
        Any aliases, typing-module aliases, and prohibited wildcard imports.
    """
    any_names: set[str] = set()
    typing_modules: set[str] = set()
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            typing_modules.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in _TYPE_MODULES
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
    return any_names, typing_modules, violations


def _direct_any_reference_violations(
    tree: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
    filename: str,
) -> list[str]:
    """Return diagnostics for direct Any names and qualified typing.Any uses.

    Args:
        tree: Parsed Python module.
        any_names: Local aliases that resolve to typing.Any.
        typing_modules: Aliases that resolve to typing or typing_extensions.
        filename: Source path used in diagnostics.

    Returns:
        Diagnostics for prohibited explicit Any references.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in any_names:
            violations.append(
                f"{filename}:{getattr(node, 'lineno', 1)}: explicit Any reference is prohibited; "
                "use a concrete type, object with narrowing, or a Protocol"
            )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "Any"
            and isinstance(node.value, ast.Name)
            and node.value.id in typing_modules
        ):
            module = node.value.id
            violations.append(
                f"{filename}:{getattr(node, 'lineno', 1)}: explicit {module}.Any reference "
                "is prohibited; use a concrete type, object with narrowing, or a Protocol"
            )
    return violations


def _annotation_fields(node: ast.AST) -> tuple[ast.AST, ...]:
    """Return annotation expressions attached to one AST node.

    Args:
        node: Function argument, function definition, or annotated assignment.

    Returns:
        Annotation expressions stored on the node.
    """
    if isinstance(node, ast.arg) and node.annotation is not None:
        return (node.annotation,)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
        return (node.returns,)
    if isinstance(node, ast.AnnAssign):
        return (node.annotation,)
    return ()


def _annotation_any_violations(
    tree: ast.AST,
    any_names: set[str],
    typing_modules: set[str],
    filename: str,
) -> list[str]:
    """Return diagnostics for stringified annotations and legacy type comments.

    Args:
        tree: Parsed Python module with type-comment parsing enabled.
        any_names: Local aliases that resolve to typing.Any.
        typing_modules: Aliases that resolve to typing or typing_extensions.
        filename: Source path used in diagnostics.

    Returns:
        Diagnostics for quoted annotations or type comments containing Any.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        for annotation in _annotation_fields(node):
            if (
                isinstance(annotation, ast.Constant)
                and isinstance(annotation.value, str)
                and _contains_explicit_any(annotation, any_names, typing_modules)
            ):
                line = getattr(annotation, "lineno", getattr(node, "lineno", 1))
                violations.append(
                    f"{filename}:{line}: stringified annotation references explicit Any; "
                    "use a concrete type, object with narrowing, or a Protocol"
                )

        type_comment = getattr(node, "type_comment", None)
        if not isinstance(type_comment, str):
            continue
        roots = _type_comment_roots(type_comment)
        if any(_contains_explicit_any(root, any_names, typing_modules) for root in roots):
            line = getattr(node, "lineno", 1)
            violations.append(
                f"{filename}:{line}: type comment references explicit Any; "
                "use a concrete type, object with narrowing, or a Protocol"
            )
    return violations


def explicit_any_violations(source: str, filename: str = "<memory>") -> tuple[str, ...]:
    """Return source locations that explicitly reference ``typing.Any``.

    Imports from ``typing`` or ``typing_extensions`` are resolved so renamed
    imports cannot bypass the rule. Wildcard imports are rejected because they
    expose ``Any`` without an explicit symbol reference. Quoted forward
    annotations and type comments are parsed only in annotation-related fields;
    ordinary user-facing strings are not interpreted as type syntax.

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

    any_names, typing_modules, violations = _typing_import_symbols(tree, filename)
    violations.extend(_direct_any_reference_violations(tree, any_names, typing_modules, filename))
    violations.extend(_annotation_any_violations(tree, any_names, typing_modules, filename))
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
    """Check every repository Python source against the AST policy contracts.

    Returns:
        Process status indicating whether explicit-Any and host-import policies pass.
    """
    any_violations: list[str] = []
    importlib_violations: list[str] = []
    count = 0
    for path in python_files():
        count += 1
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            relative = path.relative_to(ROOT)
            any_violations.append(f"{relative}: unable to read Python source: {exc}")
            continue
        relative_path = path.relative_to(ROOT).as_posix()
        any_violations.extend(explicit_any_violations(source, relative_path))
        importlib_violations.extend(literal_host_importlib_violations(source, relative_path))

    if any_violations:
        sys.stderr.write("explicit-any-policy=failed\n")
        sys.stderr.write("\n".join(sorted(any_violations)) + "\n")
    else:
        sys.stdout.write(f"explicit-any-policy=passed python_files={count}\n")

    if importlib_violations:
        sys.stderr.write("literal-host-importlib-policy=failed\n")
        sys.stderr.write("\n".join(sorted(importlib_violations)) + "\n")
    else:
        sys.stdout.write("literal-host-importlib-policy=passed\n")

    return int(bool(any_violations or importlib_violations))


if __name__ == "__main__":
    raise SystemExit(main())

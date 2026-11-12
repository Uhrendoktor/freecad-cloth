# Copyright (C) 2026 FreeCAD Cloth contributors
"""Enforce descriptive public API docs and expose generic-object annotation inspection.

Every tracked Python source and stub is checked. Ruff enforces annotation syntax and the full
compatible lint rule set; this contract verifies documentation prose and prohibits object as a
generic annotation escape hatch. Use concrete types, structural Protocols, TypedDicts, or
recursive JSON value unions instead.
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORIES = frozenset(
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
SECTION_HEADER = re.compile(
    r"^(Args|Arguments|Parameters|Returns|Yields|Raises|Attributes|Examples|Notes|Warnings):\s*$"
)
PARAMETER_LINE = re.compile(r"^\s{4}(\*{0,2}[A-Za-z_][A-Za-z0-9_]*)(?:\s+\([^)]*\))?:\s*(\S.*)$")
EXCEPTION_LINE = re.compile(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*):\s*(\S.*)$")
DESCRIPTION_WORD = re.compile(r"[A-Za-z0-9_]+")
MIN_DESCRIPTION_WORDS = 2
PLACEHOLDER = re.compile(r"\b(?:todo|tbd|fixme|placeholder|document me)\b", re.IGNORECASE)


def _expression_name(expression: ast.AST) -> str | None:
    """Return a dotted name for a Name or Attribute expression.

    Args:
        expression: AST node that may identify an imported typing symbol.

    Returns:
        Dotted identifier, or None for expressions without a static name.
    """
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        parent = _expression_name(expression.value)
        return f"{parent}.{expression.attr}" if parent is not None else None
    return None


def _is_object_reference(
    expression: ast.expr,
    builtins_modules: set[str],
    object_names: set[str],
) -> bool:
    """Determine whether a simple expression aliases the built-in object type.

    Args:
        expression: Assignment value or annotation expression to inspect.
        builtins_modules: Local aliases for the builtins module.
        object_names: Local names already known to resolve to builtins.object.

    Returns:
        True for a direct or qualified reference to builtins.object.
    """
    if isinstance(expression, ast.Name):
        return expression.id in object_names
    dotted = _expression_name(expression)
    if dotted is None:
        return False
    module, _, attribute = dotted.rpartition(".")
    return attribute == "object" and module in builtins_modules


def _record_import_aliases(
    node: ast.AST,
    builtins_modules: set[str],
    object_names: set[str],
    typing_modules: set[str],
    operators: dict[str, set[str]],
) -> None:
    """Record local names introduced by builtins and typing imports.

    Args:
        node: Import statement to inspect.
        builtins_modules: Mutable aliases for the builtins module.
        object_names: Mutable aliases for builtins.object.
        typing_modules: Mutable aliases for typing modules.
        operators: Mutable aliases for supported typing constructors.
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "builtins":
                builtins_modules.add(alias.asname or "builtins")
            elif alias.name in {"typing", "typing_extensions"}:
                typing_modules.add(alias.asname or alias.name)
        return
    if not isinstance(node, ast.ImportFrom):
        return
    if node.module == "builtins":
        object_names.update(
            alias.asname or alias.name for alias in node.names if alias.name == "object"
        )
    elif node.module in {"typing", "typing_extensions"}:
        for alias in node.names:
            if alias.name in operators:
                operators[alias.name].add(alias.asname or alias.name)


def _object_assignment_alias(
    node: ast.AST,
    builtins_modules: set[str],
    object_names: set[str],
) -> str | None:
    """Return the local target when an assignment aliases builtins.object.

    Args:
        node: AST node considered as a possible assignment.
        builtins_modules: Local aliases for the builtins module.
        object_names: Names already known to refer to builtins.object.

    Returns:
        Newly discovered alias name, or None when the node is not such an assignment.
    """
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Name) or target.id in object_names:
        return None
    if _is_object_reference(node.value, builtins_modules, object_names):
        return target.id
    return None


def _typing_context(
    tree: ast.AST,
) -> tuple[set[str], set[str], set[str], dict[str, set[str]]]:
    """Collect aliases used for builtins and standard typing operators.

    Args:
        tree: Parsed module whose import declarations define local aliases.

    Returns:
        Builtins-module aliases, object aliases, typing-module aliases, and direct
        aliases for Literal, Annotated, TypeVar, NewType, TypeAliasType, and cast.
    """
    builtins_modules = {"builtins"}
    object_names = {"object"}
    typing_modules = {"typing", "typing_extensions"}
    operators = {
        name: {name}
        for name in ("Literal", "Annotated", "TypeVar", "NewType", "TypeAliasType", "cast")
    }
    nodes = tuple(ast.walk(tree))
    for node in nodes:
        _record_import_aliases(node, builtins_modules, object_names, typing_modules, operators)

    while True:
        discovered_alias = False
        for node in nodes:
            alias = _object_assignment_alias(node, builtins_modules, object_names)
            if alias is not None:
                object_names.add(alias)
                discovered_alias = True
        if not discovered_alias:
            break
    return builtins_modules, object_names, typing_modules, operators


def _is_typing_operator(
    expression: ast.AST,
    symbol: str,
    typing_modules: set[str],
    operators: dict[str, set[str]],
) -> bool:
    """Determine whether an expression names an imported typing operator.

    Args:
        expression: Callable or generic type expression to inspect.
        symbol: Expected typing operator, such as Literal or TypeVar.
        typing_modules: Local aliases for typing and typing_extensions modules.
        operators: Local aliases for directly imported typing operators.

    Returns:
        True when the expression resolves syntactically to the requested operator.
    """
    if isinstance(expression, ast.Name):
        return expression.id in operators[symbol]
    dotted = _expression_name(expression)
    return dotted is not None and any(dotted == f"{module}.{symbol}" for module in typing_modules)


def _type_expression_items(expression: ast.expr) -> tuple[ast.expr, ...]:
    """Return the individual expressions represented by a generic type slice.

    Args:
        expression: Generic slice expression from an annotation.

    Returns:
        Tuple elements for a multi-argument slice, or the single expression itself.
    """
    if isinstance(expression, ast.Tuple):
        return tuple(expression.elts)
    return (expression,)


def _forwarded_type_expression(annotation: ast.expr) -> ast.expr | None:
    """Parse a quoted forward reference into its nested type expression.

    Args:
        annotation: Type expression that may be a quoted forward reference.

    Returns:
        Parsed inner expression, or None for non-string and nested string literals.
    """
    if not isinstance(annotation, ast.Constant) or not isinstance(annotation.value, str):
        return None
    try:
        forwarded = ast.parse(annotation.value, mode="eval").body
    except SyntaxError:
        return None
    return (
        None
        if isinstance(forwarded, ast.Constant) and isinstance(forwarded.value, str)
        else forwarded
    )


def _is_builtin_object_type(
    annotation: ast.expr,
    builtins_modules: set[str],
    object_names: set[str],
) -> bool:
    """Check whether one annotation node directly refers to builtins.object.

    Args:
        annotation: Type-expression node to inspect.
        builtins_modules: Local aliases for the builtins module.
        object_names: Local aliases for builtins.object.

    Returns:
        True when the node is the generic built-in object type.
    """
    if isinstance(annotation, ast.Name):
        return annotation.id in object_names
    if not isinstance(annotation, ast.Attribute):
        return False
    dotted = _expression_name(annotation)
    if dotted is None:
        return False
    module, _, _attribute = dotted.rpartition(".")
    return annotation.attr == "object" and module in builtins_modules


def _contains_generic_object(
    annotation: ast.expr,
    builtins_modules: set[str],
    object_names: set[str],
    typing_modules: set[str],
    operators: dict[str, set[str]],
) -> bool:
    """Detect unrestricted built-in object types inside an annotation expression.

    Args:
        annotation: Type expression attached to a declaration or typing constructor.
        builtins_modules: Local aliases for the builtins module.
        object_names: Local names resolving to builtins.object.
        typing_modules: Local aliases for typing and typing_extensions.
        operators: Local aliases for typing operators used to distinguish metadata.

    Returns:
        True when the type expression contains generic built-in object, including
        nested forward references and imported aliases.
    """
    forwarded = _forwarded_type_expression(annotation)
    if forwarded is not None:
        return _contains_generic_object(
            forwarded, builtins_modules, object_names, typing_modules, operators
        )
    if _is_builtin_object_type(annotation, builtins_modules, object_names):
        return True
    if not isinstance(annotation, ast.Subscript):
        return _contains_child_generic_object(
            annotation, builtins_modules, object_names, typing_modules, operators
        )
    if _is_typing_operator(annotation.value, "Literal", typing_modules, operators):
        return False
    if _is_typing_operator(annotation.value, "Annotated", typing_modules, operators):
        items = _type_expression_items(annotation.slice)
        return bool(items) and _contains_generic_object(
            items[0], builtins_modules, object_names, typing_modules, operators
        )
    return _contains_child_generic_object(
        annotation, builtins_modules, object_names, typing_modules, operators
    )


def _contains_child_generic_object(
    annotation: ast.expr,
    builtins_modules: set[str],
    object_names: set[str],
    typing_modules: set[str],
    operators: dict[str, set[str]],
) -> bool:
    """Inspect nested expression children for a generic object type.

    Args:
        annotation: Parent expression whose child expressions should be inspected.
        builtins_modules: Local aliases for the builtins module.
        object_names: Local aliases for builtins.object.
        typing_modules: Local aliases for typing and typing_extensions.
        operators: Local aliases for typing operators used to distinguish metadata.

    Returns:
        True when any nested expression contains generic builtins.object.
    """
    return any(
        _contains_generic_object(item, builtins_modules, object_names, typing_modules, operators)
        for item in ast.iter_child_nodes(annotation)
        if isinstance(item, ast.expr)
    )


def _type_comment_expression(comment: str) -> ast.expr | None:
    """Parse one assignment or loop type comment as a type expression.

    Args:
        comment: Type comment without its leading comment marker.

    Returns:
        Parsed expression, or None when the comment is not an expression type.
    """
    try:
        return ast.parse(comment, mode="eval").body
    except SyntaxError:
        return None


def _function_type_comment_annotations(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    annotations: list[tuple[int, str, ast.expr]],
) -> None:
    """Collect parameter and result types from a legacy function type comment.

    Args:
        node: Function declaration carrying the parsed type comment.
        annotations: Mutable annotation inventory receiving each type expression.
    """
    if not node.type_comment:
        return
    try:
        function_type = ast.parse(node.type_comment, mode="func_type")
    except SyntaxError:
        return
    annotations.extend(
        (node.lineno, f"{node.name} type-comment parameter", value)
        for value in function_type.argtypes
    )
    annotations.append((node.lineno, f"{node.name} type-comment return", function_type.returns))


def _ordinary_type_comment_annotation(
    node: ast.AST,
    annotations: list[tuple[int, str, ast.expr]],
) -> None:
    """Collect an assignment, loop, or context-manager type comment.

    Args:
        node: Statement that may carry a legacy type comment.
        annotations: Mutable annotation inventory receiving the parsed expression.
    """
    if not isinstance(node, (ast.Assign, ast.For, ast.AsyncFor, ast.With, ast.AsyncWith)):
        return
    comment = getattr(node, "type_comment", None)
    if not comment:
        return
    expression = _type_comment_expression(comment)
    if expression is not None:
        annotations.append((node.lineno, "type comment", expression))


def _typing_call_annotations(
    node: ast.Call,
    annotations: list[tuple[int, str, ast.expr]],
    typing_modules: set[str],
    operators: dict[str, set[str]],
) -> None:
    """Collect type expressions supplied to common typing constructors.

    Args:
        node: Call expression to inspect for a typing helper.
        annotations: Mutable annotation inventory receiving constructor type arguments.
        typing_modules: Local aliases for typing and typing_extensions modules.
        operators: Local aliases for supported directly imported typing helpers.
    """
    if _is_typing_operator(node.func, "TypeVar", typing_modules, operators):
        annotations.extend(
            (node.lineno, "TypeVar constraint or bound", value)
            for value in (*node.args[1:], *(keyword.value for keyword in node.keywords))
        )
    elif _is_typing_operator(node.func, "NewType", typing_modules, operators):
        annotations.extend((node.lineno, "NewType base", value) for value in node.args[1:])
    elif _is_typing_operator(node.func, "TypeAliasType", typing_modules, operators):
        annotations.extend((node.lineno, "TypeAliasType value", value) for value in node.args[1:])
    elif _is_typing_operator(node.func, "cast", typing_modules, operators) and node.args:
        annotations.append((node.lineno, "cast target type", node.args[0]))


def _object_annotation_errors(filename: str, tree: ast.AST) -> list[str]:
    """Reject generic object annotations throughout one parsed Python module.

    Args:
        filename: Source filename used in diagnostic messages.
        tree: Parsed syntax tree for the complete Python module.

    Returns:
        One actionable diagnostic for every parameter, result, field, alias, or
        supported typing-constructor use that contains built-in object as a type.
    """
    builtins_modules, object_names, typing_modules, operators = _typing_context(tree)
    annotations: list[tuple[int, str, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            annotations.append((node.annotation.lineno, node.arg, node.annotation))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                annotations.append((node.returns.lineno, f"{node.name} return value", node.returns))
            _function_type_comment_annotations(node, annotations)
        elif isinstance(node, ast.AnnAssign):
            subject = ast.unparse(node.target)
            annotations.append((node.annotation.lineno, subject, node.annotation))
            alias_kind = ast.unparse(node.annotation).rsplit(".", 1)[-1]
            if alias_kind in {"TypeAlias", "TypeAliasType"} and node.value is not None:
                annotations.append((node.value.lineno, f"{subject} type alias", node.value))
        elif isinstance(node, ast.TypeAlias):
            annotations.append((node.value.lineno, ast.unparse(node.name), node.value))
        elif isinstance(node, ast.Call):
            _typing_call_annotations(node, annotations, typing_modules, operators)
        else:
            _ordinary_type_comment_annotation(node, annotations)

    return [
        (
            f"{filename}:{line}: {subject}: generic object type annotations are prohibited; "
            "use a concrete type, Protocol, TypedDict, or recursive JSON value type"
        )
        for line, subject, annotation in annotations
        if _contains_generic_object(
            annotation, builtins_modules, object_names, typing_modules, operators
        )
    ]


def object_annotation_violations(source: str, filename: str = "<memory>") -> tuple[str, ...]:
    """Return generic built-in object type annotations without applying the prose contract.

    Args:
        source: Complete Python source or stub text to inspect.
        filename: Repository-relative diagnostic label for the supplied source.

    Returns:
        Actionable locations of built-in object type annotations, including aliases
        and supported typing constructors.
    """
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return (f"{filename}:{line}: cannot parse Python source: {exc}",)
    return tuple(_object_annotation_errors(filename, tree))


def _python_files(arguments: list[str]) -> tuple[Path, ...]:
    """Return requested Python files or the public implementation and tooling inventory.

    Args:
        arguments: Optional paths supplied by a pre-commit invocation.

    Returns:
        Existing Python source files in deterministic repository order.
    """
    if arguments:
        candidates = [Path(value) for value in arguments if value.endswith(".py")]
    else:
        candidates = list((ROOT / "freecad_cloth").rglob("*.py"))
        candidates.extend((ROOT / "tools").rglob("*.py"))
    return tuple(sorted(path if path.is_absolute() else ROOT / path for path in candidates))


def _requires_api_docs(path: Path) -> bool:
    """Select production modules whose public APIs require contract docstrings.

    Args:
        path: Python source path being checked.

    Returns:
        True for public domain modules, excluding dynamically registered GUI and command files.
    """
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    return (
        relative.parts[0] == "freecad_cloth"
        and path.name not in {"workbench.py", "gui.py"}
        and not path.name.endswith(("Gui.py", "Commands.py"))
    )


def _display_path(path: Path) -> str:
    """Format a path relative to the repository when possible.

    Args:
        path: Absolute or relative source path.

    Returns:
        Stable repository-relative path or the original path.
    """
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def check_source(
    source: str,
    filename: str = "<memory>",
    *,
    public_api_only: bool = False,
    module_only: bool = False,
) -> list[str]:
    """Validate documentation prose and suppression policy for one Python source.

    Args:
        source: Complete Python source text.
        filename: File label shown in diagnostic messages.
        public_api_only: Limit declaration checks to public module-level APIs and methods
            on public classes.
        module_only: Skip declaration checks while retaining module and suppression checks.

    Returns:
        All documentation and suppression violations found.
    """
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        return [f"{filename}: cannot parse Python source: {exc}"]

    errors = suppression_violations(source, filename)
    if not filename.endswith(".pyi") and ast.get_docstring(tree) is None:
        errors.append(f"{filename}: missing module docstring")

    if module_only:
        declarations: list[ast.AST] = []
    elif public_api_only:
        declarations = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                declarations.append(node)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                declarations.append(node)
                declarations.extend(
                    member
                    for member in node.body
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not member.name.startswith("_")
                )
    else:
        declarations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]

    for node in declarations:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            errors.extend(_function_errors(filename, node))
        elif isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            if docstring is None:
                errors.append(f"{filename}:{node.lineno}: {node.name}: missing class docstring")
            else:
                label = _label(filename, node.lineno, node.name)
                errors.extend(_summary_errors(label, node.name, docstring))
    return sorted(errors)


def check(path: Path) -> list[str]:
    """Return documentation contract violations for a Python source file.

    Args:
        path: Python source or stub file.

    Returns:
        All violations in source order.
    """
    filename = _display_path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{filename}: cannot read Python source: {exc}"]
    return check_source(
        source,
        filename,
        public_api_only=_requires_api_docs(path),
        module_only=not _requires_api_docs(path),
    )


def main() -> int:
    """Check all selected Python files and write actionable diagnostics.

    Returns:
        Zero when all source files satisfy the contract, otherwise one.
    """
    errors = [error for path in _python_files(sys.argv[1:]) for error in check(path)]
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
        return 1
    sys.stdout.write("documentation-contract=passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

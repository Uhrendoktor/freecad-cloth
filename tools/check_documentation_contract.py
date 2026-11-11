# Copyright (C) 2026 FreeCAD Cloth contributors
"""Enforce descriptive Python docs and reject generic object type annotations.

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


def _python_files(arguments: list[str]) -> tuple[Path, ...]:
    """Return requested paths or all repository Python sources in stable order.

    Args:
        arguments: Optional source paths supplied by a pre-commit invocation.

    Returns:
        Unique existing Python source and stub paths in deterministic order.
    """
    if arguments:
        candidates = [Path(value) for value in arguments if value.endswith((".py", ".pyi"))]
    else:
        candidates: list[Path] = []
        for directory, names, filenames in os.walk(ROOT):
            names[:] = sorted(name for name in names if name not in IGNORED_DIRECTORIES)
            candidates.extend(
                Path(directory) / name for name in filenames if name.endswith((".py", ".pyi"))
            )

    paths = {
        (candidate if candidate.is_absolute() else ROOT / candidate).resolve()
        for candidate in candidates
    }
    return tuple(sorted(path for path in paths if path.is_file()))


def _label(filename: str, line: int, name: str) -> str:
    """Build a stable file-and-line diagnostic label.

    Args:
        filename: Source file path used by the checker.
        line: One-based source line for the declaration.
        name: Name of the documented module, class, or function.

    Returns:
        Human-readable diagnostic prefix.
    """
    return f"{filename}:{line}: {name}"


def _sections(docstring: str) -> dict[str, tuple[str, ...]]:
    """Split a Google-style docstring into its named sections.

    Args:
        docstring: Cleaned docstring text from the syntax tree.

    Returns:
        Section names mapped to their body lines.
    """
    lines = docstring.splitlines()
    sections: dict[str, tuple[str, ...]] = {}
    index = 0
    while index < len(lines):
        heading = lines[index].strip()
        if not SECTION_HEADER.fullmatch(heading):
            index += 1
            continue
        name = heading[:-1]
        end = index + 1
        while end < len(lines) and not SECTION_HEADER.fullmatch(lines[end].strip()):
            end += 1
        sections[name] = tuple(lines[index + 1 : end])
        index = end
    return sections


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Collect function parameters whose meaning must be documented.

    Args:
        node: Function or method syntax node.

    Returns:
        Parameter names excluding conventional self and cls receivers.
    """
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        arguments.append(node.args.vararg)
    if node.args.kwarg is not None:
        arguments.append(node.args.kwarg)
    return {argument.arg for argument in arguments if argument.arg not in {"self", "cls"}}


def _documented_parameters(lines: tuple[str, ...]) -> dict[str, str]:
    """Collect parameter names and their descriptions from an Args section.

    Args:
        lines: Body lines belonging to a Google-style Args section.

    Returns:
        Parameter names mapped to the descriptions supplied for them.
    """
    descriptions: dict[str, str] = {}
    for line in lines:
        match = PARAMETER_LINE.match(line)
        if match:
            descriptions[match.group(1).lstrip("*")] = match.group(2).strip()
    return descriptions


def _description_is_weak(description: str, subject: str | None = None) -> bool:
    """Determine whether prose is empty, generic, or repeats its documented name.

    Args:
        description: Candidate prose from a docstring section.
        subject: Optional parameter or exception name the prose must explain.

    Returns:
        Whether the text is too short, generic, or repeats the subject name.
    """
    normalized = re.sub(r"[*_]", "", description).strip().rstrip(".!?").casefold()
    words = DESCRIPTION_WORD.findall(normalized)
    repeats_subject = subject is not None and normalized in {
        subject.casefold(),
        subject.replace("_", " ").casefold(),
    }
    return (
        len(words) < MIN_DESCRIPTION_WORDS
        or PLACEHOLDER.search(description) is not None
        or repeats_subject
    )


def _current_scope(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.AST, ...]:
    """Walk a function body without attributing nested declarations to it.

    Args:
        node: Function whose directly executed body should be inspected.

    Returns:
        Descendant syntax nodes excluding nested functions, classes, and lambdas.
    """
    pending: list[ast.AST] = list(node.body)
    visited: list[ast.AST] = []
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        visited.append(current)
        pending.extend(ast.iter_child_nodes(current))
    return tuple(visited)


def _summary_errors(label: str, name: str, docstring: str) -> list[str]:
    """Reject empty summaries and summaries that merely repeat the symbol.

    Args:
        label: File-and-line diagnostic prefix.
        name: Name of the documented symbol.
        docstring: Cleaned docstring to validate.

    Returns:
        Summary-specific documentation errors.
    """
    summary = next((line.strip() for line in docstring.splitlines() if line.strip()), "")
    if not summary or PLACEHOLDER.search(summary):
        return [f"{label}: summary must describe behavior and must not be a placeholder"]
    normalized = summary.rstrip(".!?").strip().casefold()
    if normalized in {name.casefold(), name.replace("_", " ").casefold()}:
        return [f"{label}: summary must describe behavior instead of repeating the symbol name"]
    return []


def _argument_errors(
    label: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    sections: dict[str, tuple[str, ...]],
) -> list[str]:
    """Require meaningful prose for every explicit function parameter.

    Args:
        label: File-and-line diagnostic prefix.
        node: Function or method syntax node.
        sections: Parsed docstring sections.

    Returns:
        Argument-documentation errors.
    """
    parameters = _parameter_names(node)
    if not parameters:
        return []
    if "Args" not in sections:
        return [f"{label}: missing Args section for {', '.join(sorted(parameters))}"]
    documented = _documented_parameters(sections["Args"])
    missing = parameters - documented.keys()
    if missing:
        return [f"{label}: missing parameter descriptions for {', '.join(sorted(missing))}"]
    weak = {
        parameter
        for parameter in parameters
        if _description_is_weak(documented[parameter], parameter)
    }
    if weak:
        return [f"{label}: non-descriptive parameter descriptions for {', '.join(sorted(weak))}"]
    return []


def _return_errors(
    label: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    sections: dict[str, tuple[str, ...]],
    scope: tuple[ast.AST, ...],
) -> list[str]:
    """Require prose describing non-None results and yielded values.

    Args:
        label: File-and-line diagnostic prefix.
        node: Function or method syntax node.
        sections: Parsed docstring sections.
        scope: Syntax nodes from the function's own execution scope.

    Returns:
        Return or yield documentation errors.
    """
    if node.returns is None:
        return []
    return_type = ast.unparse(node.returns).strip().strip("'\"")
    if return_type in {"None", "NoneType", "NoReturn", "Never"}:
        return []
    generator = any(isinstance(item, (ast.Yield, ast.YieldFrom)) for item in scope)
    section = "Yields" if generator else "Returns"
    description = " ".join(line.strip() for line in sections.get(section, ()) if line.strip())
    if not description:
        return [f"{label}: missing descriptive {section} section for {return_type}"]
    if _description_is_weak(description):
        return [f"{label}: {section} description is too vague or contains a placeholder"]
    return []


def _exception_name(expression: ast.expr) -> str | None:
    """Extract a statically named exception class from a raise expression.

    Args:
        expression: The exception expression used by a raise statement.

    Returns:
        Explicit exception class name, or None when it cannot be determined.
    """
    target = expression.func if isinstance(expression, ast.Call) else expression
    if isinstance(target, ast.Name) and target.id[:1].isupper():
        return target.id
    if isinstance(target, ast.Attribute) and target.attr[:1].isupper():
        return target.attr
    return None


def _raises_errors(
    label: str,
    scope: tuple[ast.AST, ...],
    sections: dict[str, tuple[str, ...]],
) -> list[str]:
    """Require exception descriptions for explicit raise statements.

    Args:
        label: File-and-line diagnostic prefix.
        scope: Syntax nodes from the function's own execution scope.
        sections: Parsed docstring sections.

    Returns:
        Errors for omitted or incomplete Raises sections.
    """
    raised = {
        name
        for item in scope
        if isinstance(item, ast.Raise) and item.exc is not None
        if (name := _exception_name(item.exc)) is not None
    }
    has_explicit_raise = any(isinstance(item, ast.Raise) and item.exc is not None for item in scope)
    if not has_explicit_raise:
        return []
    lines = sections.get("Raises", ())
    if not any(line.strip() for line in lines):
        return [f"{label}: missing descriptive Raises section"]
    documented = {
        match.group(1): match.group(2).strip()
        for line in lines
        if (match := EXCEPTION_LINE.match(line)) is not None
    }
    missing = raised - documented.keys()
    if missing:
        return [f"{label}: Raises must describe {', '.join(sorted(missing))}"]
    weak = {name for name in raised if _description_is_weak(documented[name], name)}
    if weak:
        return [f"{label}: non-descriptive Raises entries for {', '.join(sorted(weak))}"]
    return []


def _function_errors(
    filename: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """Validate the complete docstring contract of a function or method.

    Args:
        filename: Source filename used in diagnostic messages.
        node: Function or method syntax node to validate.

    Returns:
        Documentation contract errors for this declaration.
    """
    label = _label(filename, node.lineno, node.name)
    docstring = ast.get_docstring(node)
    if docstring is None:
        return [f"{label}: missing docstring"]
    sections = _sections(docstring)
    scope = _current_scope(node)
    errors = _summary_errors(label, node.name, docstring)
    errors.extend(_argument_errors(label, node, sections))
    errors.extend(_return_errors(label, node, sections, scope))
    errors.extend(_raises_errors(label, scope, sections))
    return errors


def suppression_violations(source: str, filename: str = "<memory>") -> list[str]:
    """Reject comments that disable Ruff diagnostics.

    Args:
        source: Python source text being inspected.
        filename: Source filename used in diagnostics.

    Returns:
        One error per inline or file-wide Ruff noqa comment.
    """
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        return [
            f"{filename}:{token.start[0]}: Ruff noqa suppressions are prohibited; fix the source"
            for token in tokens
            if token.type == tokenize.COMMENT
            and re.search(r"\bnoqa\b", token.string, re.IGNORECASE)
        ]
    except (tokenize.TokenError, IndentationError) as exc:
        return [f"{filename}: cannot inspect comments: {exc}"]


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


def check_source(source: str, filename: str = "<memory>") -> list[str]:
    """Validate documentation structure for one Python source string.

    Args:
        source: Complete Python source text.
        filename: File label shown in diagnostics.

    Returns:
        All documentation and suppression violations found.
    """
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        return [f"{filename}: cannot parse Python source: {exc}"]

    errors = suppression_violations(source, filename)
    errors.extend(_object_annotation_errors(filename, tree))
    # Stub files are declarations, not prose modules; Ruff's pyi rules prohibit docstrings.
    if not filename.endswith(".pyi") and ast.get_docstring(tree) is None:
        errors.append(f"{filename}: missing module docstring")
    for node in ast.walk(tree):
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
    return check_source(source, filename)


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

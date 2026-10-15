# Copyright (C) 2026 FreeCAD Cloth contributors
"""Enforce descriptive, complete Python documentation without lint suppressions.

Every tracked Python source and stub is checked. Ruff enforces type annotations and
the full compatible lint rule set; this contract verifies prose for function
parameters, return values, yielded values, and explicitly raised exceptions.
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
EXCEPTION_LINE = re.compile(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*):\s*\S")
PLACEHOLDER = re.compile(r"\b(?:todo|tbd|fixme|placeholder|document me)\b", re.IGNORECASE)


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
        candidates = []
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


def _documented_parameters(lines: tuple[str, ...]) -> set[str]:
    """Collect parameter names with non-empty Args descriptions.

    Args:
        lines: Body lines belonging to a Google-style Args section.

    Returns:
        Parameter names for which a description is present.
    """
    names: set[str] = set()
    for line in lines:
        match = PARAMETER_LINE.match(line)
        if match:
            names.add(match.group(1).lstrip("*"))
    return names


def _current_scope(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.AST, ...]:
    """Walk a function body without attributing nested declarations to it.

    Args:
        node: Function whose directly executed body should be inspected.

    Returns:
        Descendant syntax nodes excluding nested functions, classes, and lambdas.
    """
    pending = list(node.body)
    visited: list[ast.AST] = []
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        visited.append(current)
        pending.extend(ast.iter_child_nodes(current))
    return tuple(visited)


def _summary_errors(label: str, name: str, docstring: str) -> list[str]:
    """Reject placeholder summaries and summaries that just repeat the symbol.

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
    missing = parameters - _documented_parameters(sections["Args"])
    if missing:
        return [f"{label}: missing parameter descriptions for {', '.join(sorted(missing))}"]
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
    if section not in sections or not any(line.strip() for line in sections[section]):
        return [f"{label}: missing descriptive {section} section for {return_type}"]
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
        match.group(1) for line in lines if (match := EXCEPTION_LINE.match(line)) is not None
    }
    missing = raised - documented
    if missing:
        return [f"{label}: Raises must describe {', '.join(sorted(missing))}"]
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
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [f"{filename}: cannot parse Python source: {exc}"]

    errors = suppression_violations(source, filename)
    if ast.get_docstring(tree) is None:
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

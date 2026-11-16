# Copyright (C) 2026 FreeCAD Cloth contributors
"""Require Pydantic validation for production data-carrier dataclasses."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT: Final = ROOT / "freecad_cloth"
EXPECTED_TEST_REFERENCE_PARTS: Final = 2

# Every exception must name the concrete serialization incompatibility and the
# regression test that proves why a Pydantic record cannot be used.
FREECAD_SERIALIZATION_EXCEPTIONS: Final[dict[str, tuple[str, str]]] = {}


def _dataclass_import_aliases(
    tree: ast.Module,
) -> tuple[set[str], set[str]]:
    """Collect imported aliases for stdlib dataclass decorators.

    Args:
        tree: Parsed Python module containing the imports to inspect.

    Returns:
        Imported names for dataclass and aliases for the dataclasses module.
    """
    dataclass_names: set[str] = set()
    dataclasses_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            dataclass_names.update(
                alias.asname or "dataclass"
                for alias in node.names
                if alias.name in {"dataclass", "*"}
            )
        elif isinstance(node, ast.Import):
            dataclasses_modules.update(
                alias.asname or alias.name for alias in node.names if alias.name == "dataclasses"
            )
    return dataclass_names, dataclasses_modules


def _uses_stdlib_dataclass(
    decorator: ast.expr,
    dataclass_names: set[str],
    dataclasses_modules: set[str],
) -> bool:
    """Return whether one decorator resolves to the stdlib dataclass helper.

    Args:
        decorator: Decorator expression attached to a class.
        dataclass_names: Imported symbol aliases for dataclass.
        dataclasses_modules: Imported module aliases for dataclasses.

    Returns:
        True when the decorator refers to a standard-library dataclass.
    """
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    uses_imported_symbol = isinstance(target, ast.Name) and target.id in dataclass_names
    uses_imported_module = (
        isinstance(target, ast.Attribute)
        and target.attr == "dataclass"
        and isinstance(target.value, ast.Name)
        and target.value.id in dataclasses_modules
    )
    return uses_imported_symbol or uses_imported_module


def standard_dataclass_decorators(
    source: str,
    filename: str = "<unknown>",
) -> tuple[str, ...]:
    """Return locations that decorate production records with stdlib dataclasses.

    Args:
        source: Python source whose class decorators must be inspected.
        filename: Source label included in parse and policy diagnostics.

    Returns:
        Sorted diagnostics for classes using standard-library dataclasses.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return (f"{filename}:{error.lineno or 1}: invalid Python syntax: {error.msg}",)

    dataclass_names, dataclasses_modules = _dataclass_import_aliases(tree)
    violations = [
        (
            f"{filename}:{decorator.lineno}: {node.name} uses stdlib dataclasses; "
            "use pydantic.dataclasses.dataclass or pydantic.BaseModel"
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for decorator in node.decorator_list
        if _uses_stdlib_dataclass(decorator, dataclass_names, dataclasses_modules)
    ]
    return tuple(sorted(violations))


def _test_contains_named_declaration(tree: ast.Module, name: str) -> bool:
    """Check whether a test module defines the exception's referenced regression test.

    Args:
        tree: Parsed test module to inspect.
        name: Required test function, async function, or test class name.

    Returns:
        True when a declaration with the requested name exists.
    """
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == name
        for node in ast.walk(tree)
    )


def _serialization_reason_is_specific(reason: str) -> bool:
    """Check whether an exemption identifies a FreeCAD serialization incompatibility.

    Args:
        reason: Human-readable reason recorded for a serialization exception.

    Returns:
        True only when the reason names FreeCAD, serialization, and incompatibility.
    """
    normalized = reason.casefold()
    required_terms = ("freecad", "serialization", "incompatib")
    return all(term in normalized for term in required_terms)


def _test_reference_is_valid(test_reference: list[str]) -> bool:
    """Check the repository path and declaration name in an exemption reference.

    Args:
        test_reference: Parts split from a tests-path and test-name reference.

    Returns:
        True when exactly one test module and a named test declaration are supplied.
    """
    if len(test_reference) != EXPECTED_TEST_REFERENCE_PARTS:
        return False
    test_path, test_name = test_reference
    return test_path.startswith("tests/") and test_name.startswith("test_")


def serialization_exception_is_justified(
    path: str, *, exceptions: dict[str, tuple[str, str]] | None = None
) -> bool:
    """Require a concrete FreeCAD serialization reason and an existing regression test.

    Args:
        path: Repository-relative production module path.
        exceptions: Optional exception inventory override used by contract tests.

    Returns:
        True only when the exception and its referenced regression test are valid.
    """
    configured_exceptions = FREECAD_SERIALIZATION_EXCEPTIONS if exceptions is None else exceptions
    exception = configured_exceptions.get(path)
    if exception is None:
        return False
    reason, regression_test = exception
    test_reference = regression_test.split("#", maxsplit=1)
    if not _serialization_reason_is_specific(reason) or not _test_reference_is_valid(
        test_reference
    ):
        return False
    test_path = ROOT / test_reference[0]
    if not test_path.is_file():
        return False
    try:
        test_tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=regression_test)
    except (OSError, SyntaxError):
        return False
    return _test_contains_named_declaration(test_tree, test_reference[1])


def repository_violations() -> tuple[str, ...]:
    """Check all production Python modules and fail closed on syntax errors.

    Returns:
        Sorted diagnostics for production dataclasses without justified exemptions.
    """
    violations: list[str] = []
    for path in sorted(PRODUCTION_ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        found = standard_dataclass_decorators(source, relative)
        if found and not serialization_exception_is_justified(relative):
            violations.extend(found)
    return tuple(violations)


def main() -> int:
    """Enforce Pydantic-backed production data models.

    Returns:
        Zero after successful validation.

    Raises:
        SystemExit: If a production module violates the Pydantic model policy.
    """
    violations = repository_violations()
    if violations:
        raise SystemExit("\n".join(violations))
    print("pydantic-model-policy=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

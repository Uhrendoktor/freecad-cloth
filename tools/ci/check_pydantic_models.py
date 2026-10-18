"""Require Pydantic validation for production data-carrier dataclasses."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT: Final = ROOT / "freecad_cloth"

# Every exception must name the concrete serialization incompatibility and the
# regression test that proves why a Pydantic record cannot be used.
FREECAD_SERIALIZATION_EXCEPTIONS: Final[dict[str, tuple[str, str]]] = {}


def standard_dataclass_decorators(
    source: str,
    filename: str = "<unknown>",
) -> tuple[str, ...]:
    """Find production classes decorated with standard-library dataclasses.

    Args:
        source: Python source text containing class definitions.
        filename: Display name used for source-location diagnostics.

    Returns:
        Sorted violation descriptions for forbidden dataclass decorators.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return (f"{filename}:{error.lineno or 1}: invalid Python syntax: {error.msg}",)

    dataclass_names: set[str] = set()
    dataclasses_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            for alias in node.names:
                if alias.name == "dataclass" or alias.name == "*":
                    dataclass_names.add(alias.asname or "dataclass")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dataclasses":
                    dataclasses_modules.add(alias.asname or alias.name)

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            uses_stdlib_dataclass = isinstance(target, ast.Name) and target.id in dataclass_names
            uses_module_dataclass = (
                isinstance(target, ast.Attribute)
                and target.attr == "dataclass"
                and isinstance(target.value, ast.Name)
                and target.value.id in dataclasses_modules
            )
            if uses_stdlib_dataclass or uses_module_dataclass:
                violations.append(
                    f"{filename}:{target.lineno}: {node.name} uses stdlib dataclasses; "
                    "use pydantic.dataclasses.dataclass or pydantic.BaseModel"
                )
    return tuple(sorted(violations))


def serialization_exception_is_justified(
    path: str, *, exceptions: dict[str, tuple[str, str]] | None = None
) -> bool:
    """Check that a dataclass exception is justified by a verified FreeCAD limitation.

    Args:
        path: Repository-relative Python path under consideration.
        exceptions: Optional map of paths to incompatibility reasons and test references.

    Returns:
        True only when the reason names the FreeCAD serialization incompatibility
        and the referenced regression test exists and parses successfully.
    """
    configured_exceptions = FREECAD_SERIALIZATION_EXCEPTIONS if exceptions is None else exceptions
    exception = configured_exceptions.get(path)
    if exception is None:
        return False
    reason, regression_test = exception
    normalized_reason = reason.casefold()
    test_reference = regression_test.split("#", maxsplit=1)
    if (
        "freecad" not in normalized_reason
        or "serialization" not in normalized_reason
        or "incompatib" not in normalized_reason
        or len(test_reference) != 2
        or not test_reference[0].startswith("tests/")
        or not test_reference[1].startswith("test_")
    ):
        return False
    test_path = ROOT / test_reference[0]
    if not test_path.is_file():
        return False
    try:
        test_tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=regression_test)
    except (OSError, SyntaxError):
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == test_reference[1]
        for node in ast.walk(test_tree)
    )


def repository_violations() -> tuple[str, ...]:
    """Collect prohibited standard-library dataclass decorators in production modules.

    Returns:
        Violation descriptions for production classes that use a forbidden
        decorator without a documented serialization exception.
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
    """Run the repository policy for validated production data models.

    Raises:
        SystemExit: If a production class uses a prohibited dataclass decorator.

    Returns:
        Zero when all production data carriers follow the Pydantic policy.
    """
    violations = repository_violations()
    if violations:
        raise SystemExit("\n".join(violations))
    print("pydantic-model-policy=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

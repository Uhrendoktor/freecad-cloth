"""Require Pydantic validation for production data-carrier dataclasses."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT: Final = ROOT / "freecad_cloth"

# An entry is allowed only for a demonstrated incompatibility with FreeCAD's
# own serialized document representation. Keep the list empty unless a concrete
# serialized field cannot be represented by a Pydantic model/dataclass.
FREECAD_SERIALIZATION_EXCEPTIONS: Final[dict[str, str]] = {}


def standard_dataclass_decorators(
    source: str,
    filename: str = "<unknown>",
) -> tuple[str, ...]:
    """Return locations that decorate production records with stdlib dataclasses."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return (f"{filename}:{error.lineno or 1}: invalid Python syntax: {error.msg}",)

    dataclass_names: set[str] = set()
    dataclasses_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            for alias in node.names:
                if alias.name == "dataclass":
                    dataclass_names.add(alias.asname or alias.name)
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


def serialization_exception_is_justified(path: str) -> bool:
    """Require any compatibility exception to name the exact FreeCAD serialization blocker."""
    reason = FREECAD_SERIALIZATION_EXCEPTIONS.get(path, "").casefold()
    return "freecad" in reason and "serialization" in reason and "incompatib" in reason


def repository_violations() -> tuple[str, ...]:
    """Check all production Python modules and fail closed on syntax errors."""
    violations: list[str] = []
    for path in sorted(PRODUCTION_ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        found = standard_dataclass_decorators(source, relative)
        if found and not serialization_exception_is_justified(relative):
            violations.extend(found)
    return tuple(violations)


def main() -> int:
    """Enforce Pydantic-backed production data models."""
    violations = repository_violations()
    if violations:
        raise SystemExit("\n".join(violations))
    print("pydantic-model-policy=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reject explicit ``Any`` references throughout repository Python sources.

Ruff ANN401 checks function parameters and returns. This syntax-aware gate also
catches aliases, local variables, and class attributes that the Ruff rule does
not cover.
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


def explicit_any_violations(source: str, filename: str = "<memory>") -> tuple[str, ...]:
    """Return source locations that explicitly reference ``typing.Any``.

    Imports from ``typing`` or ``typing_extensions`` are resolved so renamed
    imports cannot bypass the rule. Wildcard imports are rejected because they
    expose ``Any`` without an explicit symbol reference.
    """
    try:
        tree = ast.parse(source, filename=filename)
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

#!/usr/bin/env python3
"""Check the repository's persistent Python API documentation contract."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXEMPT_API_FILES = {"workbench.py", "gui.py"}


def _python_files(arguments: list[str]) -> tuple[Path, ...]:
    if arguments:
        paths = [Path(value) for value in arguments if value.endswith(".py")]
    else:
        paths = list((ROOT / "freecad_cloth").rglob("*.py")) + list((ROOT / "tools").rglob("*.py"))
    return tuple(sorted(path if path.is_absolute() else ROOT / path for path in paths))


def _requires_api_docs(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        relative.parts[0] in {"freecad_cloth", "tools"}
        and path.name not in EXEMPT_API_FILES
        and not path.name.endswith(("Gui.py", "Commands.py"))
    )


def check(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [f"{path}: cannot parse: {exc}"]

    errors = []
    if ast.get_docstring(tree) is None:
        errors.append(f"{path}: missing module docstring")

    if not _requires_api_docs(path):
        return errors

    for node in tree.body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and not node.name.startswith("_"):
            if ast.get_docstring(node) is None:
                errors.append(
                    f"{path}:{node.lineno}: missing docstring for public {type(node).__name__.lower()} {node.name}"
                )
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for member in node.body:
                if (
                    isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not member.name.startswith("_")
                    and ast.get_docstring(member) is None
                ):
                    errors.append(
                        f"{path}:{member.lineno}: missing docstring for public method {node.name}.{member.name}"
                    )
    return errors


def main() -> int:
    errors = [error for path in _python_files(sys.argv[1:]) for error in check(path)]
    if errors:
        print("\n".join(errors))
        return 1
    print("documentation-contract=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

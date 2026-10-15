"""Reject test-time monkeypatching and global module replacement."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _is_sys_modules(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "modules"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _targets(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.Assign):
        return tuple(node.targets)
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.Delete)):
        target = node.target if hasattr(node, "target") else None
        if target is not None:
            return (target,)
        return tuple(node.targets)
    return ()


def python_monkeypatch_violations(source: str, filename: str = "<source>") -> tuple[str, ...]:
    """Return forbidden fixture, mock patch, import cache, and module rewrites."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return (f"{filename}:{exc.lineno}: cannot audit invalid Python syntax: {exc.msg}",)

    violations: list[str] = []
    module_aliases: set[str] = set()
    in_tests = filename.replace("\\", "/").startswith("tests/")

    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.arg == "monkeypatch":
            violations.append(
                f"{filename}:{node.lineno}: pytest monkeypatch fixtures are forbidden; inject dependencies"
            )
        elif isinstance(node, ast.Name) and node.id == "monkeypatch":
            violations.append(
                f"{filename}:{node.lineno}: pytest monkeypatch is forbidden; inject dependencies"
            )
        elif isinstance(node, ast.Attribute) and node.attr == "MonkeyPatch":
            violations.append(
                f"{filename}:{node.lineno}: pytest.MonkeyPatch is forbidden; inject dependencies"
            )

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "unittest.mock":
                    violations.append(
                        f"{filename}:{node.lineno}: unittest.mock patching is forbidden; inject dependencies"
                    )
                bound = alias.asname or alias.name.split(".", maxsplit=1)[0]
                if in_tests:
                    module_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "unittest.mock" or (
                node.module == "unittest" and any(alias.name == "mock" for alias in node.names)
            ):
                violations.append(
                    f"{filename}:{node.lineno}: unittest.mock patching is forbidden; inject dependencies"
                )
            if (
                in_tests
                and node.module
                and (node.module.startswith("freecad_cloth.") or node.module.startswith("tools."))
            ):
                module_aliases.update(alias.asname or alias.name for alias in node.names)

        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.Delete)):
            for target in _targets(node):
                if isinstance(target, ast.Subscript) and _is_sys_modules(target.value):
                    violations.append(
                        f"{filename}:{node.lineno}: sys.modules mutation is forbidden; inject dependencies"
                    )
                elif (
                    in_tests
                    and isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in module_aliases
                ):
                    violations.append(
                        f"{filename}:{node.lineno}: replacing an imported module attribute is forbidden; inject dependencies"
                    )

        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Attribute)
                and _is_sys_modules(node.func.value)
                and node.func.attr not in {"get", "__contains__", "__getitem__"}
            ):
                violations.append(
                    f"{filename}:{node.lineno}: sys.modules mutation is forbidden; inject dependencies"
                )
            if (
                in_tests
                and isinstance(node.func, ast.Name)
                and node.func.id == "setattr"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in module_aliases
            ):
                violations.append(
                    f"{filename}:{node.lineno}: replacing an imported module attribute is forbidden; inject dependencies"
                )

    return tuple(sorted(set(violations)))


def repository_violations(root: Path = ROOT) -> tuple[str, ...]:
    """Audit every tracked-style Python source under the repository root."""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"{relative}: cannot read source for monkeypatch audit: {exc}")
            continue
        violations.extend(python_monkeypatch_violations(source, relative))
    return tuple(sorted(violations))


def main() -> int:
    """Fail CI when prohibited monkeypatching patterns are found."""
    violations = repository_violations()
    if violations:
        raise SystemExit("\n".join(violations))
    print("monkeypatch-policy=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

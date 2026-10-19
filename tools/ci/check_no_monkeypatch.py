# Copyright (C) 2026 FreeCAD Cloth contributors
"""Reject test-time monkeypatching and global module replacement."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _is_sys_modules(node: ast.AST) -> bool:
    """Identify an AST attribute expression that names the sys.modules attribute.

    Args:
        node: Expression to classify.

    Returns:
        True when the node is the sys.modules attribute, otherwise False.
    """
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "modules"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _targets(node: ast.AST) -> tuple[ast.AST, ...]:
    """Extract assignment targets from an AST mutation statement.

    Args:
        node: Assignment, deletion, or augmented-assignment node to inspect.

    Returns:
        All target expressions exposed by the node, or an empty tuple when none exist.
    """
    if isinstance(node, ast.Assign):
        return tuple(node.targets)
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.Delete)):
        target = node.target if hasattr(node, "target") else None
        if target is not None:
            return (target,)
        return tuple(node.targets)
    return ()


def _record_forbidden_symbols(
    node: ast.AST,
    filename: str,
    violations: list[str],
) -> None:
    """Record use of prohibited patching symbols on one AST node.

    Args:
        node: Syntax node being inspected.
        filename: Source filename used in diagnostic locations.
        violations: Mutable diagnostic collection.
    """
    if isinstance(node, ast.arg) and node.arg == "monkeypatch":
        violations.append(
            f"{filename}:{node.lineno}: pytest monkeypatch fixtures are forbidden; "
            "inject dependencies"
        )
    elif isinstance(node, ast.Name) and node.id == "monkeypatch":
        violations.append(
            f"{filename}:{node.lineno}: pytest monkeypatch is forbidden; inject dependencies"
        )
    elif isinstance(node, ast.Attribute) and node.attr == "MonkeyPatch":
        violations.append(
            f"{filename}:{node.lineno}: pytest.MonkeyPatch is forbidden; inject dependencies"
        )


def _record_import_violations(
    node: ast.AST,
    filename: str,
    in_tests: bool,
    module_aliases: set[str],
    violations: list[str],
) -> None:
    """Record patch-related imports and names that could be mutated in tests.

    Args:
        node: Import syntax node being inspected.
        filename: Source filename used in diagnostic locations.
        in_tests: Whether the source file is under the tests directory.
        module_aliases: Mutable set of local names referring to imported modules.
        violations: Mutable diagnostic collection.
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "unittest.mock":
                violations.append(
                    f"{filename}:{node.lineno}: unittest.mock patching is forbidden; "
                    "inject dependencies"
                )
            bound = alias.asname or alias.name.split(".", maxsplit=1)[0]
            if in_tests:
                module_aliases.add(bound)
        return
    if not isinstance(node, ast.ImportFrom):
        return

    imports_mock = node.module == "unittest.mock" or (
        node.module == "unittest" and any(alias.name == "mock" for alias in node.names)
    )
    if imports_mock:
        violations.append(
            f"{filename}:{node.lineno}: unittest.mock patching is forbidden; inject dependencies"
        )
    imports_repository_modules = (
        in_tests
        and node.module is not None
        and (node.module.startswith("freecad_cloth.") or node.module.startswith("tools."))
    )
    if imports_repository_modules:
        module_aliases.update(alias.asname or alias.name for alias in node.names)


def _is_imported_module_attribute(target: ast.AST, module_aliases: set[str]) -> bool:
    """Return whether a target replaces an attribute on an imported module.

    Args:
        target: Assignment target to classify.
        module_aliases: Local names referring to imported modules.

    Returns:
        Whether the target mutates an imported module's attribute.
    """
    if not isinstance(target, ast.Attribute):
        return False
    if not isinstance(target.value, ast.Name):
        return False
    return target.value.id in module_aliases


def _record_assignment_violations(
    node: ast.AST,
    filename: str,
    in_tests: bool,
    module_aliases: set[str],
    violations: list[str],
) -> None:
    """Record mutations of sys.modules and imported module attributes.

    Args:
        node: Syntax node representing a possible assignment or deletion.
        filename: Source filename used in diagnostic locations.
        in_tests: Whether the source file is under the tests directory.
        module_aliases: Local names referring to imported modules.
        violations: Mutable diagnostic collection.
    """
    for target in _targets(node):
        if isinstance(target, ast.Subscript) and _is_sys_modules(target.value):
            violations.append(
                f"{filename}:{node.lineno}: sys.modules mutation is forbidden; inject dependencies"
            )
        elif in_tests and _is_imported_module_attribute(target, module_aliases):
            violations.append(
                f"{filename}:{node.lineno}: replacing an imported module attribute is forbidden; "
                "inject dependencies"
            )


def _is_sys_modules_mutation_call(node: ast.Call) -> bool:
    """Return whether a call mutates sys.modules rather than reading it.

    Args:
        node: Call syntax node to classify.

    Returns:
        Whether the call invokes a mutating sys.modules method.
    """
    if not isinstance(node.func, ast.Attribute) or not _is_sys_modules(node.func.value):
        return False
    return node.func.attr not in {"get", "__contains__", "__getitem__"}


def _is_module_replacement_setattr(
    node: ast.Call,
    in_tests: bool,
    module_aliases: set[str],
) -> bool:
    """Return whether setattr targets an imported module in a test.

    Args:
        node: Call syntax node to classify.
        in_tests: Whether the source file is under the tests directory.
        module_aliases: Local names referring to imported modules.

    Returns:
        Whether the call would replace a module attribute inside a test.
    """
    if not in_tests or not isinstance(node.func, ast.Name):
        return False
    if node.func.id != "setattr" or not node.args:
        return False
    target = node.args[0]
    return isinstance(target, ast.Name) and target.id in module_aliases


def _record_call_violations(
    node: ast.AST,
    filename: str,
    in_tests: bool,
    module_aliases: set[str],
    violations: list[str],
) -> None:
    """Record mutating calls to sys.modules and imported modules.

    Args:
        node: Syntax node that may contain a mutation call.
        filename: Source filename used in diagnostic locations.
        in_tests: Whether the source file is under the tests directory.
        module_aliases: Local names referring to imported modules.
        violations: Mutable diagnostic collection.
    """
    if not isinstance(node, ast.Call):
        return
    if _is_sys_modules_mutation_call(node):
        violations.append(
            f"{filename}:{node.lineno}: sys.modules mutation is forbidden; inject dependencies"
        )
    if _is_module_replacement_setattr(node, in_tests, module_aliases):
        violations.append(
            f"{filename}:{node.lineno}: replacing an imported module attribute is forbidden; "
            "inject dependencies"
        )


def python_monkeypatch_violations(source: str, filename: str = "<source>") -> tuple[str, ...]:
    """Report prohibited monkeypatching and module-replacement patterns.

    Args:
        source: Python source text to parse and inspect.
        filename: Display name used for source-location diagnostics.

    Returns:
        Sorted, duplicate-free violation descriptions for the supplied source.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return (f"{filename}:{line}: cannot audit invalid Python syntax: {exc.msg}",)

    violations: list[str] = []
    module_aliases: set[str] = set()
    in_tests = filename.replace("\\", "/").startswith("tests/")

    for node in ast.walk(tree):
        _record_forbidden_symbols(node, filename, violations)
        _record_import_violations(node, filename, in_tests, module_aliases, violations)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.Delete)):
            _record_assignment_violations(node, filename, in_tests, module_aliases, violations)
        _record_call_violations(node, filename, in_tests, module_aliases, violations)
    return tuple(sorted(set(violations)))

def repository_violations(root: Path = ROOT) -> tuple[str, ...]:
    """Scan repository Python sources for prohibited monkeypatching patterns.

    Args:
        root: Repository directory whose Python files will be audited.

    Returns:
        Sorted violation descriptions for all readable Python files under the root.
    """
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
    """Run the repository monkeypatch policy gate.

    Returns:
        Zero when all inspected Python sources satisfy the policy.

    Raises:
        SystemExit: If one or more prohibited mutation patterns are found.
    """
    violations = repository_violations()
    if violations:
        raise SystemExit("\n".join(violations))
    sys.stdout.write("monkeypatch-policy=passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

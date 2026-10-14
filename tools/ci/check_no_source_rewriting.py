"""Reject runtime rewriting or generated execution of checked-in Python source."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_NAME_HINTS = {
    "source",
    "source_text",
    "python_source",
    "source_code",
    "script_source",
}
WRITE_METHODS = {"write_text", "write_bytes"}
READ_METHODS = {"read_text", "read_bytes", "read"}
INLINE_EDIT_COMMANDS = (
    re.compile(r"(?im)\bsed\s+-i(?:\S*)?\b"),
    re.compile(r"(?im)\b(?:perl|ruby)\s+-[^\s]*p[^\s]*i[^\s]*\b"),
)
INLINE_PYTHON_EDIT = re.compile(
    r"(?i)\bpython(?:3(?:\.\d+)?)?\s+-c\b[^\n]*(?:\.replace\s*\(|\.write_text\s*\(|\.write_bytes\s*\()"
)


def _target_names(target: ast.expr) -> set[str]:
    """Return simple variable names assigned by one assignment target."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for element in target.elts:
            result.update(_target_names(element))
        return result
    return set()


def _contains_python_path_literal(node: ast.AST) -> bool:
    """Recognize path expressions that explicitly identify a Python source file."""
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and (child.value.endswith(".py") or child.value.endswith(".pyi"))
        ):
            return True
        if isinstance(child, ast.Name) and child.id == "__file__":
            return True
    return False


def _read_method_receiver(node: ast.AST) -> ast.expr | None:
    """Return the receiver of a read call, if this node represents file reading."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr not in READ_METHODS:
        return None
    return node.func.value


def _names_used(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _checked_in_source_handles(
    tree: ast.Module, python_path_names: set[str]
) -> set[str]:
    """Find file handles opened from known Python paths inside with statements."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        for item in node.items:
            expression = item.context_expr
            if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
                continue
            if expression.func.id != "open" or not expression.args:
                continue
            source_path = expression.args[0]
            if _names_used(source_path) & python_path_names or _contains_python_path_literal(
                source_path
            ):
                names.update(_target_names(item.optional_vars) if item.optional_vars else set())
    return names


def _is_checked_in_source_expression(
    expression: ast.expr,
    source_names: set[str],
    python_path_names: set[str],
) -> bool:
    """Return whether an expression reads unchanged text from a known Python file."""
    if isinstance(expression, ast.Name):
        return expression.id in source_names
    receiver = _read_method_receiver(expression)
    return receiver is not None and bool(
        _names_used(receiver) & (python_path_names | source_names)
        or _contains_python_path_literal(receiver)
    )


def python_source_rewrite_violations(source_text: str, path: str = "<source>") -> tuple[str, ...]:
    """Find Python-source replacement, file-write, and dynamic execution patterns."""
    try:
        tree = ast.parse(source_text, filename=path)
    except SyntaxError as error:
        return (f"{path}:{error.lineno or 1}: invalid Python syntax: {error.msg}",)

    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
    ]
    python_path_names: set[str] = set()
    for node in assignments:
        value = node.value
        if value is not None and _contains_python_path_literal(value):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                python_path_names.update(_target_names(target))

    source_names = _checked_in_source_handles(tree, python_path_names)
    modified_source_names: set[str] = set()
    for _ in range(4):
        changed = False
        for node in assignments:
            value = node.value
            if value is None:
                continue
            read_receiver = _read_method_receiver(value)
            if read_receiver is not None:
                receiver_names = _names_used(read_receiver)
                if (
                    receiver_names & python_path_names
                    or _contains_python_path_literal(read_receiver)
                    or (
                        _target_names(node.targets[0])
                        if isinstance(node, ast.Assign)
                        else _target_names(node.target)
                    )
                    & PYTHON_SOURCE_NAME_HINTS
                ):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        before = len(source_names)
                        source_names.update(_target_names(target))
                        changed |= len(source_names) != before
            if isinstance(value, ast.Call):
                rewrites_source = False
                if isinstance(value.func, ast.Attribute) and value.func.attr == "replace":
                    rewrites_source = bool(_names_used(value.func.value) & source_names)
                elif (
                    isinstance(value.func, ast.Attribute) and value.func.attr in {"sub", "subn"}
                ) or (isinstance(value.func, ast.Name) and value.func.id in {"sub", "subn"}):
                    rewrites_source = any(
                        _names_used(argument) & source_names for argument in value.args
                    )
                if rewrites_source:
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        before = len(modified_source_names)
                        modified_source_names.update(_target_names(target))
                        changed |= len(modified_source_names) != before
            if isinstance(value, ast.BinOp) and _names_used(value) & (
                source_names | modified_source_names
            ):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    before = len(modified_source_names)
                    modified_source_names.update(_target_names(target))
                    changed |= len(modified_source_names) != before
        if not changed:
            break

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name) and node.func.id == "exec" and node.args:
            expression = node.args[0]
            if _names_used(expression) & modified_source_names:
                violations.append(
                    f"{path}:{node.lineno}: transformed source must not be executed dynamically"
                )
            elif isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name):
                if expression.func.id == "compile" and expression.args:
                    compiled_source = expression.args[0]
                    if _names_used(compiled_source) & modified_source_names:
                        violations.append(
                            f"{path}:{node.lineno}: transformed source must not be executed dynamically"
                        )
                    elif (
                        isinstance(compiled_source, ast.Name)
                        and compiled_source.id not in source_names
                    ) or (
                        isinstance(compiled_source, (ast.Constant, ast.BinOp, ast.JoinedStr))
                        and not (_names_used(compiled_source) & source_names)
                    ):
                        violations.append(
                            f"{path}:{node.lineno}: generated Python source must not be executed"
                        )
            elif isinstance(expression, (ast.Constant, ast.BinOp, ast.JoinedStr)):
                if not (_names_used(expression) & source_names):
                    violations.append(
                        f"{path}:{node.lineno}: generated Python source must not be executed"
                    )
            elif isinstance(expression, ast.Name) and expression.id not in source_names:
                violations.append(
                    f"{path}:{node.lineno}: generated Python source must not be executed"
                )

        if isinstance(node.func, ast.Attribute):
            receiver_names = _names_used(node.func.value)
            rewrites_source = (
                node.func.attr == "replace" and bool(receiver_names & source_names)
            ) or (
                node.func.attr in {"sub", "subn"}
                and any(_names_used(argument) & source_names for argument in node.args)
            )
            if rewrites_source:
                violations.append(
                    f"{path}:{node.lineno}: Python source text must not be rewritten with "
                    f"{node.func.attr}(); use explicit functions/configuration"
                )
            if node.func.attr in WRITE_METHODS and (
                _names_used(node) & (source_names | modified_source_names)
            ):
                violations.append(
                    f"{path}:{node.lineno}: Python source text must not be written after "
                    "runtime transformation"
                )

        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"sub", "subn"}
            and any(_names_used(argument) & source_names for argument in node.args)
        ):
            violations.append(
                f"{path}:{node.lineno}: Python source text must not be rewritten with "
                f"{node.func.id}(); use explicit functions/configuration"
            )

        if isinstance(node.func, ast.Name) and node.func.id == "compile" and node.args:
            expression = node.args[0]
            if _names_used(expression) & modified_source_names or (
                isinstance(expression, ast.BinOp) and _names_used(expression) & source_names
            ):
                violations.append(
                    f"{path}:{node.lineno}: transformed source must not be compiled at runtime"
                )
            elif not _is_checked_in_source_expression(expression, source_names, python_path_names):
                violations.append(
                    f"{path}:{node.lineno}: compiling generated Python source is prohibited"
                )

    return tuple(sorted(set(violations)))


def workflow_source_rewrite_violations(text: str, path: str = "<workflow>") -> tuple[str, ...]:
    """Reject inline shell commands that rewrite tracked source/configuration files."""
    violations: list[str] = []
    for pattern in INLINE_EDIT_COMMANDS:
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            violations.append(
                f"{path}:{line}: inline in-place editing is prohibited; make a reviewed commit"
            )
    for match in INLINE_PYTHON_EDIT.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        violations.append(
            f"{path}:{line}: inline Python source/config rewriting is prohibited; "
            "use reviewed repository changes"
        )
    return tuple(sorted(set(violations)))


def _policy_files() -> tuple[Path, ...]:
    """Return repository Python sources and executable CI configuration files."""
    python_files = [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in {".git", ".venv", "__pycache__", "build", "dist"} for part in path.parts)
    ]
    ci_files = list((ROOT / ".github").rglob("*.yml"))
    ci_files.extend((ROOT / ".github").rglob("*.yaml"))
    ci_files.extend((ROOT / "tools").rglob("*.sh"))
    ci_files.extend((ROOT / ".github").rglob("*.sh"))
    return tuple(sorted({*python_files, *ci_files}))


def main() -> int:
    """Scan the repository and fail closed on forbidden source manipulation."""
    errors: list[str] = []
    for path in _policy_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            errors.extend(python_source_rewrite_violations(text, relative))
        elif path.suffix in {".yml", ".yaml", ".sh"}:
            errors.extend(workflow_source_rewrite_violations(text, relative))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("source-rewriting-policy=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

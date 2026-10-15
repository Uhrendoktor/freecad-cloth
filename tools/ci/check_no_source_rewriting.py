"""Reject source-code rewriting in Python and inline CI commands."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOTS = ("freecad_cloth", "tests", "tools", "freecad")
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
PYTHON_SOURCE_SUFFIXES = {".py", ".pyi"}
WORKFLOW_ROOTS = (".github/workflows", ".github/actions")
SOURCE_PATCH_METHODS = {"replace", "sub", "subn"}


def _contains_python_path_literal(node: ast.AST) -> bool:
    """Return whether an expression visibly names a Python source file."""
    return any(
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and Path(value.value).suffix in PYTHON_SOURCE_SUFFIXES
        for value in ast.walk(node)
    )


def _target_names(node: ast.AST) -> tuple[str, ...]:
    """Return the simple variable targets assigned by one statement."""
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(name for item in node.elts for name in _target_names(item))
    return ()


def python_source_rewrite_violations(source: str, filename: str = "<source>") -> tuple[str, ...]:
    """Find string-based transformations of Python files loaded as source text."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return (f"{filename}:{error.lineno}: invalid Python syntax: {error.msg}",)

    python_path_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None or not _contains_python_path_literal(value):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                python_path_names.update(_target_names(target))

    source_text_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        value = node.value
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        reads_python_source = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr in {"read_text", "read"}
            and (
                any(
                    isinstance(child, ast.Name) and child.id in python_path_names
                    for child in ast.walk(value)
                )
                or _contains_python_path_literal(value)
            )
        )
        if reads_python_source:
            for target in targets:
                source_text_names.update(_target_names(target))

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        patch_name = ""
        candidate_text: ast.AST | None = None
        if isinstance(func, ast.Attribute) and func.attr in SOURCE_PATCH_METHODS:
            patch_name = func.attr
            if func.attr == "replace":
                candidate_text = func.value
            elif len(node.args) >= 3:
                # Module-level re.sub takes pattern, replacement, then the source string.
                is_regex_module = isinstance(func.value, ast.Name) and func.value.id in {
                    "re",
                    "regex",
                }
                candidate_text = node.args[2] if is_regex_module else node.args[1]
            elif len(node.args) >= 2:
                candidate_text = node.args[1]
            else:
                candidate_text = next(
                    (
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg in {"string", "text", "source"}
                    ),
                    None,
                )
        elif isinstance(func, ast.Name) and func.id in {"sub", "subn"}:
            patch_name = func.id
            if len(node.args) >= 3:
                candidate_text = node.args[2]
            else:
                candidate_text = next(
                    (
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg in {"string", "text", "source"}
                    ),
                    None,
                )
        if candidate_text is None:
            continue

        receiver_is_source = (
            isinstance(candidate_text, ast.Name) and candidate_text.id in source_text_names
        )
        receiver_is_python_read = (
            isinstance(candidate_text, ast.Call)
            and isinstance(candidate_text.func, ast.Attribute)
            and candidate_text.func.attr in {"read_text", "read"}
            and (
                any(
                    isinstance(child, ast.Name) and child.id in python_path_names
                    for child in ast.walk(candidate_text)
                )
                or _contains_python_path_literal(candidate_text)
            )
        )
        if receiver_is_source or receiver_is_python_read:
            violations.append(
                f"{filename}:{node.lineno}: do not transform loaded Python source with "
                f"{patch_name}(); use ordinary functions/configuration instead"
            )
    return tuple(violations)


def _workflow_run_blocks(text: str) -> tuple[tuple[int, str], ...]:
    """Return complete YAML run-script blocks with their starting line numbers."""
    lines = text.splitlines()
    blocks: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)(?:-\s*)?run\s*:\s*(.*)$", lines[index])
        if match is None:
            index += 1
            continue
        indentation = len(match.group(1))
        value = match.group(2).strip()
        block_lines = [value] if value else []
        start_line = index + 1
        index += 1
        if value and not re.fullmatch(r"[|>][+-]?", value):
            blocks.append((start_line, value))
            continue
        while index < len(lines):
            line = lines[index]
            if line.strip() and len(line) - len(line.lstrip()) <= indentation:
                break
            block_lines.append(line)
            index += 1
        blocks.append((start_line, "\n".join(block_lines)))
    return tuple(blocks)


def workflow_source_rewrite_violations(text: str, filename: str = "<workflow>") -> tuple[str, ...]:
    """Find workflow scripts that patch tracked Python or configuration files."""
    violations = []
    for line_number, script in _workflow_run_blocks(text):
        inline_python = re.search(
            r"\bpython(?:3)?\s+-c\b|\bpython(?:3)?\s+(?:-\s*)?<<",
            script,
        )
        in_place_editor = re.search(r"\b(?:sed\s+-i|perl\s+-pi|ruby\s+-pi|ed\s+-s)\b", script)
        source_write = re.search(
            r"\.write_text\s*\(|\.write_bytes\s*\(|\.replace\s*\(|\bopen\s*\([^\n]*(?:['\"]w|['\"]a)",
            script,
        )
        tracked_path = re.search(
            r"""['"][^'"]+\.(?:py|pyi|toml|yaml|yml)['"]|pyrightconfig\.json|\.github/workflows/""",
            script,
        )
        checkout_patch = re.search(
            r"\bgit\s+(?:checkout|restore)\b[^\n]*--[^\n]*"
            r"(?:\.pyi?|\.toml|\.ya?ml|pyrightconfig\.json|\.github/workflows/)",
            script,
        )
        if (
            (inline_python and source_write and tracked_path)
            or (in_place_editor and tracked_path)
            or checkout_patch
        ):
            violations.append(
                f"{filename}:{line_number}: workflow edits tracked source/configuration; "
                "commit the intended change normally instead"
            )
    return tuple(violations)


def check_repository(root: Path = ROOT) -> tuple[str, ...]:
    """Scan repository Python source plus workflow/action definitions."""
    errors: list[str] = []
    for root_name in PYTHON_ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                errors.append(f"{path}: cannot read Python source: {error}")
                continue
            errors.extend(python_source_rewrite_violations(text, path.relative_to(root).as_posix()))
    for path in (root / "Init.py", root / "InitGui.py", root / "sitecustomize.py"):
        if path.is_file():
            errors.extend(
                python_source_rewrite_violations(
                    path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()
                )
            )

    for root_name in WORKFLOW_ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        candidates = list(base.rglob("*.yml")) + list(base.rglob("*.yaml"))
        for path in sorted(set(candidates)):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                errors.append(f"{path}: cannot read workflow source: {error}")
                continue
            errors.extend(
                workflow_source_rewrite_violations(text, path.relative_to(root).as_posix())
            )
    return tuple(errors)


def main() -> int:
    """Run the blocking repository source-rewriting policy."""
    errors = check_repository()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("source-rewriting-policy=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

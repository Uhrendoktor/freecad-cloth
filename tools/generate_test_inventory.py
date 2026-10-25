# Copyright (C) 2026 FreeCAD Cloth contributors
"""Generate individual test-case entries in the developer test inventory."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = REPOSITORY_ROOT / "tests"
INVENTORY_PATH = REPOSITORY_ROOT / "docs" / "developers" / "TEST_INVENTORY.md"
SECTION_HEADING = "## Individual test cases"
MAX_GOAL_LENGTH = 220
DOCSTRING_HEADINGS = {"Args:", "Returns:", "Raises:", "Notes:", "Examples:"}


def _test_goal(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return a concise goal for one test function.

    Args:
        function: Parsed test function or method.

    Returns:
        The first descriptive docstring line, or a readable fallback based on
        the test function name.
    """
    docstring = ast.get_docstring(function) or ""
    goal = next((line.strip() for line in docstring.splitlines() if line.strip()), "")
    if not goal or goal in DOCSTRING_HEADINGS:
        name = function.name.removeprefix("test_").replace("_", " ")
        goal = f"Exercise {name}."
    goal = re.sub(r"\s+", " ", goal).replace("`", "'").replace("|", r"\|")
    return goal[:MAX_GOAL_LENGTH]


def _test_functions(source: Path) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Parse test declarations from one Python source file.

    Args:
        source: Python test file to inspect.

    Returns:
        Test function and method declarations sorted by source order.
    """
    syntax = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    functions = [
        node
        for node in ast.walk(syntax)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    return sorted(functions, key=lambda node: (node.lineno, node.col_offset))


def _case_entries() -> list[str]:
    """Build one documented inventory entry for every test declaration.

    Returns:
        Sorted Markdown list entries with a goal and a pruning rationale.
    """
    entries = []
    test_files = sorted(TEST_ROOT.rglob("*.py"))
    for source in test_files:
        relative = source.relative_to(TEST_ROOT)
        if relative.name == "__init__.py" or relative.parts[0] == "support":
            continue
        source_path = source.relative_to(REPOSITORY_ROOT).as_posix()
        for function in _test_functions(source):
            goal = _test_goal(function)
            useful = (
                f"Makes `{function.name}` independently discoverable for regression triage "
                "and helps reviewers identify duplicate or obsolete cases."
            )
            entries.append(
                f"- `{source_path}::{function.name}` — **Goal:** {goal} "
                f"**Why useful:** {useful}"
            )
    return entries


def _updated_inventory(current: str, entries: list[str]) -> str:
    """Replace the generated test-case section while preserving module entries.

    Args:
        current: Existing inventory document.
        entries: Regenerated individual-case Markdown entries.

    Returns:
        The complete inventory with the generated section at the end.

    Raises:
        ValueError: If the generated section is not the document's final section
            or if no test declarations were found.
    """
    if not entries:
        msg = "no test_* declarations were found; refusing to empty the inventory"
        raise ValueError(msg)
    marker = f"\n{SECTION_HEADING}\n"
    section_index = current.find(marker)
    if section_index >= 0:
        remainder = current[section_index + len(marker):]
        if re.search(r"^## ", remainder, flags=re.MULTILINE):
            msg = "the individual test-case section must remain the final inventory section"
            raise ValueError(msg)
        current = current[:section_index]
    generated = (
        f"{SECTION_HEADING}\n\n"
        "This section is generated from test declarations and the first descriptive line of "
        "each test docstring. Do not edit case entries manually; run "
        "`python tools/generate_test_inventory.py` to regenerate them. When a test has no "
        "docstring, its goal is derived from the function name. Each entry is separately "
        "searchable so redundant or obsolete cases can be identified during review.\n\n"
        + "\n".join(entries)
        + "\n"
    )
    return current.rstrip() + "\n\n" + generated


def main() -> None:
    """Regenerate the case-level section of the test inventory.

    Raises:
        OSError: If the inventory cannot be read or written.
        SyntaxError: If a test file contains invalid Python syntax.
        ValueError: If inventory generation finds no cases or invalid section order.
    """
    current = INVENTORY_PATH.read_text(encoding="utf-8")
    updated = _updated_inventory(current, _case_entries())
    if current != updated:
        INVENTORY_PATH.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()

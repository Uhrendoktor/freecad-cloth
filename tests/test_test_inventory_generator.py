# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for generated test-case inventory synchronization."""

from tests.support.assertions import require
from tools import generate_test_inventory


def _first_difference(current: str, regenerated: str) -> str:
    """Describe the first textual mismatch between checked-in and generated inventory.

    Args:
        current: Checked-in inventory contents.
        regenerated: Inventory contents generated from the current test tree.

    Returns:
        A concise expected-versus-actual diagnostic, or a line-count summary.
    """
    current_lines = current.splitlines()
    generated_lines = regenerated.splitlines()
    for index, generated_line in enumerate(generated_lines):
        current_line = current_lines[index] if index < len(current_lines) else "<missing>"
        if generated_line != current_line:
            return f"expected {generated_line!r}; found {current_line!r}"
    if len(current_lines) != len(generated_lines):
        return f"expected {len(generated_lines)} lines; found {len(current_lines)}"
    return "no textual difference found"


def test_case_inventory_matches_ast_generated_entries() -> None:
    """Keep one documented entry for each test declaration and preserve module entries."""
    current = generate_test_inventory.INVENTORY_PATH.read_text(encoding="utf-8")
    regenerated = generate_test_inventory.updated_inventory(
        current,
        generate_test_inventory.case_entries(),
    )
    require(
        condition=regenerated == current,
        message=(
            "test inventory case entries are stale; run python tools/generate_test_inventory.py; "
            f"first mismatch: {_first_difference(current, regenerated)}"
        ),
    )

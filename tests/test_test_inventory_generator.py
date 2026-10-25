# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for generated test-case inventory synchronization."""

from tests.support.assertions import require
from tools import generate_test_inventory


def test_case_inventory_matches_ast_generated_entries() -> None:
    """Keep one documented entry for each test declaration and preserve module entries."""
    current = generate_test_inventory.INVENTORY_PATH.read_text(encoding="utf-8")
    regenerated = generate_test_inventory.updated_inventory(
        current,
        generate_test_inventory.case_entries(),
    )
    require(
        condition=regenerated == current,
        message="test inventory case entries are stale; run python tools/generate_test_inventory.py",
    )

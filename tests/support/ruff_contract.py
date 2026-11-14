# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared assertions for the reviewed repository Ruff configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

from tests.support.assertions import require


def assert_reviewed_ruff_policy(project_file: Path) -> None:
    """Require the project to retain its reviewed Ruff rules and precise exceptions.

    Args:
        project_file: Repository pyproject.toml whose Ruff section is validated.
    """
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))
    lint = project["tool"]["ruff"]["lint"]
    allowed_ignores = {"E402"}
    allowed_per_file = {
        "tests/**/*.py": ["S101"],
        "freecad_cloth/pattern/PatternCommands.py": ["BLE001"],
        "freecad_cloth/pattern/PatternTopologyRepairGui.py": ["BLE001"],
        "freecad_cloth/simulation/RealtimePreview.py": ["BLE001"],
        "freecad_cloth/simulation/SimulationQualityGui.py": ["BLE001"],
        "tests/freecad_*.py": ["BLE001"],
        "tests/support/pbd_contact_helpers.py": ["BLE001"],
        "tools/benchmark_workbenches.py": ["BLE001"],
        "tools/ci/python_validation.py": ["BLE001"],
    }
    require(
        condition=lint.get("select") == ["ALL"],
        message="Ruff must select every rule for all tracked Python sources and stubs.",
    )
    require(
        condition=lint.get("preview") is True,
        message="Ruff preview rules must remain enabled repository-wide.",
    )
    require(
        condition=set(lint.get("ignore", [])) == allowed_ignores,
        message="Only the documented FreeCAD loader import-order exception may remain globally ignored.",
    )
    require(
        condition=lint.get("per-file-ignores") == allowed_per_file,
        message="Per-file exceptions must remain limited to pytest assertions and exact native callback boundaries.",
    )

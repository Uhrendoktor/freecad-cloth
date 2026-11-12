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
    allowed_select = {
        "E", "F", "W", "I", "A", "ANN401", "B", "BLE", "C4", "DTZ",
        "FURB", "G", "LOG", "PERF", "PGH", "PIE", "RET", "RUF", "SIM", "UP", "YTT",
    }
    allowed_ignores = {
        "E402", "E501", "UP031", "RUF007", "RUF046", "RUF005", "RET501", "RET503",
        "RET504", "SIM105", "C401", "C408", "C416", "FURB162", "FURB192", "PIE810",
        "RUF043", "UP017", "UP040",
    }
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
        condition=set(lint.get("select", [])) == allowed_select,
        message="Ruff selection must match the reviewed correctness/security/import/type policy.",
    )
    require(
        condition=not lint.get("preview", False),
        message="Blanket Ruff preview selection is not permitted.",
    )
    require(
        condition=set(lint.get("ignore", [])) == allowed_ignores,
        message="Ruff ignores must match the reviewed rule-specific policy.",
    )
    require(
        condition=lint.get("per-file-ignores") == allowed_per_file,
        message="Only documented pytest and FreeCAD host-callback exceptions may be scoped per file.",
    )

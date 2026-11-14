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
    allowed_ignores: set[str] = set()
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
    bootstrap_paths = {
        "tools/ci/check_visual_assets_and_budget.py",
        "tools/ci/validate_acceptance.py",
        "tests/test_pattern_marks.py",
        "tests/test_command_adapter.py",
        "tests/test_meshpart_adapter.py",
        "tests/test_sewing_repair.py",
        "tests/test_simulation_gui.py",
        "tests/freecad_meshpart_smoke.py",
        "tests/freecad_workbench_benchmark.py",
        "tests/freecad_tunic_audit_production.py",
        "tests/test_core.py",
        "tests/test_sewing_network_gui_contract.py",
        "tests/test_derived_geometry.py",
        "tests/test_sewing_gui_contract.py",
        "tests/freecad_pattern_workbench_smoke.py",
        "tests/freecad_avatar_smoke.py",
        "tests/test_sewing_correspondence.py",
        "tests/test_seam_graph.py",
        "tests/drape_backend_micro.py",
        "tests/freecad_e2e.py",
        "tests/test_sewing_network.py",
        "tests/test_sewing_show2d.py",
        "tests/test_pattern_ir.py",
        "tests/freecad_drape_debug.py",
        "tests/test_freecad_objects.py",
        "tests/freecad_surface_pen_smoke.py",
        "tests/freecad_avatar_acceptance.py",
        "tests/freecad_pbd_cube_ladder.py",
        "tests/freecad_pbd_ladder_bootstrap.py",
        "tests/freecad_pbd_avatar_ladder.py",
        "tests/freecad_sketcher_acceptance.py",
        "tests/freecad_visual_examples.py",
        "tests/test_sewing_network_gui.py",
        "tests/freecad_avatar_screenshot.py",
        "tests/freecad_smoke.py",
        "tests/freecad_sewing_smoke.py",
    }
    expected_per_file = {
        "tests/**/*.py": ["S101"],
        **{path: ["E402"] for path in bootstrap_paths},
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
        condition=lint.get("per-file-ignores") == expected_per_file,
        message="Per-file exceptions must remain limited to exact bootstraps, pytest assertions, and native callbacks.",
    )

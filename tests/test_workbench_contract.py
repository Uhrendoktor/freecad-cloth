# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral checks for the package-owned Cloth workbenches."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_cloth.pattern.workbench import ClothPatternWorkbench
    from freecad_cloth.sewing.workbench import ClothSewingWorkbench
    from freecad_cloth.simulation.workbench import ClothSimulationWorkbench


def _workbenches() -> tuple[
    tuple[
        type[ClothPatternWorkbench | ClothSewingWorkbench | ClothSimulationWorkbench],
        str,
    ],
    ...,
]:
    """Import workbench classes lazily so headless test collection stays import-safe.

    Returns:
        Workbench classes paired with their user-facing menu labels.
    """
    from freecad_cloth.pattern.workbench import ClothPatternWorkbench
    from freecad_cloth.sewing.workbench import ClothSewingWorkbench
    from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

    return (
        (ClothPatternWorkbench, "Cloth Pattern"),
        (ClothSewingWorkbench, "Cloth Sewing"),
        (ClothSimulationWorkbench, "Cloth Simulation"),
    )


def test_workbench_metadata_and_resources_are_runtime_objects() -> None:
    """Validate user-facing workbench metadata and installed icon resources."""
    for cls, menu in _workbenches():
        class_name = cls.__name__
        workbench = cls()
        assert workbench.MenuText == menu, f"{class_name} exposes unexpected menu text."
        assert bool(workbench.ToolTip), f"{class_name} must provide a non-empty tooltip."
        assert workbench.GetClassName() == "Gui::PythonWorkbench", (
            f"{class_name} must be registered as a Python workbench."
        )
        assert Path(workbench.Icon).is_file(), (
            f"{class_name} icon must resolve to an existing file."
        )
        assert workbench.commands == [], (
            f"{class_name} should start with no commands before initialization."
        )


def test_package_workbench_initializers_are_import_safe_and_unique() -> None:
    """Verify each package workbench initializes a non-empty unique command list."""
    for cls, _menu in _workbenches():
        class_name = cls.__name__
        workbench = cls()
        workbench.Initialize()
        assert bool(workbench.commands), f"{class_name} must register at least one command."
        assert len(workbench.commands) == len(set(workbench.commands)), (
            f"{class_name} must not register duplicate commands."
        )


def test_simulation_workbench_registers_drape_and_simulation_surfaces() -> None:
    """Keep core commands registered; import locally to isolate this startup contract."""
    from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

    workbench = ClothSimulationWorkbench()
    workbench.Initialize()
    required_commands = (
        "ClothSimulation_CreateDrape",
        "ClothSimulation_Step",
        "ClothDrape_EditTarget",
    )
    for command in required_commands:
        assert command in workbench.commands, (
            f"Simulation workbench is missing required command {command!r}."
        )

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral checks for the package-owned Cloth workbenches."""

import importlib
from pathlib import Path

from tests.support.assertions import require

_WORKBENCHES = (
    ("freecad_cloth.pattern.workbench", "ClothPatternWorkbench", "Cloth Pattern"),
    ("freecad_cloth.sewing.workbench", "ClothSewingWorkbench", "Cloth Sewing"),
    ("freecad_cloth.simulation.workbench", "ClothSimulationWorkbench", "Cloth Simulation"),
)


def test_workbench_metadata_and_resources_are_runtime_objects() -> None:
    """Validate user-facing workbench metadata and installed icon resources."""
    for module_name, class_name, menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        require(
            condition=workbench.MenuText == menu,
            message=f"{class_name} exposes unexpected menu text.",
        )
        require(
            condition=bool(workbench.ToolTip),
            message=f"{class_name} must provide a non-empty tooltip.",
        )
        require(
            condition=workbench.GetClassName() == "Gui::PythonWorkbench",
            message=f"{class_name} must be registered as a Python workbench.",
        )
        require(
            condition=Path(workbench.Icon).is_file(),
            message=f"{class_name} icon must resolve to an existing file.",
        )
        require(
            condition=workbench.commands == [],
            message=f"{class_name} should start with no commands before initialization.",
        )


def test_package_workbench_initializers_are_import_safe_and_unique() -> None:
    """Verify each package workbench initializes a non-empty unique command list."""
    for module_name, class_name, _menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        workbench.Initialize()
        require(
            condition=bool(workbench.commands),
            message=f"{class_name} must register at least one command.",
        )
        require(
            condition=len(workbench.commands) == len(set(workbench.commands)),
            message=f"{class_name} must not register duplicate commands.",
        )


def test_simulation_workbench_registers_drape_and_simulation_surfaces() -> None:
    """Keep core commands registered; import locally to isolate this startup contract."""
    from freecad_cloth.simulation.workbench import (  # noqa: PLC0415
        ClothSimulationWorkbench,
    )

    workbench = ClothSimulationWorkbench()
    workbench.Initialize()
    required_commands = (
        "ClothSimulation_CreateDrape",
        "ClothSimulation_Step",
        "ClothDrape_EditTarget",
    )
    for command in required_commands:
        require(
            condition=command in workbench.commands,
            message=f"Simulation workbench is missing required command {command!r}.",
        )

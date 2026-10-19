# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral checks for the package-owned Cloth workbenches."""

import importlib
from pathlib import Path

_WORKBENCHES = (
    ("freecad_cloth.pattern.workbench", "ClothPatternWorkbench", "Cloth Pattern"),
    ("freecad_cloth.sewing.workbench", "ClothSewingWorkbench", "Cloth Sewing"),
    ("freecad_cloth.simulation.workbench", "ClothSimulationWorkbench", "Cloth Simulation"),
)


def _check(condition: object, message: str) -> None:
    """Raise a descriptive test failure when a required condition is false.

    Args:
        condition: Observed predicate that must hold for the contract.
        message: Explanation identifying the violated workbench contract.

    Raises:
        AssertionError: If the supplied predicate is false.
    """
    if not condition:
        raise AssertionError(message)


def test_workbench_metadata_and_resources_are_runtime_objects() -> None:
    """Verify workbench metadata and resources are exposed by runtime objects."""
    for module_name, class_name, menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        _check(workbench.MenuText == menu, f"{module_name} menu title must match its contract")
        _check(bool(workbench.ToolTip), f"{module_name} tooltip must not be empty")
        _check(
            workbench.GetClassName() == "Gui::PythonWorkbench",
            f"{module_name} must identify as a FreeCAD Python workbench",
        )
        _check(Path(workbench.Icon).is_file(), f"{module_name} icon path must exist")
        _check(workbench.commands == [], f"{module_name} must start with no registered commands")


def test_package_workbench_initializers_are_import_safe_and_unique() -> None:
    """Verify package workbench initialization produces unique command registrations."""
    for module_name, class_name, _menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        workbench.Initialize()
        _check(bool(workbench.commands), f"{module_name} must register commands")
        _check(
            len(workbench.commands) == len(set(workbench.commands)),
            f"{module_name} must not register duplicate commands",
        )


def test_simulation_workbench_registers_drape_and_simulation_surfaces() -> None:
    """Verify simulation registration includes both drape and simulation commands."""
    cls = importlib.import_module("freecad_cloth.simulation.workbench").ClothSimulationWorkbench
    workbench = cls()
    workbench.Initialize()
    _check(
        "ClothSimulation_CreateDrape" in workbench.commands,
        "simulation workbench must register the drape creation command",
    )
    _check(
        "ClothSimulation_Step" in workbench.commands,
        "simulation workbench must register the step command",
    )
    _check(
        "ClothDrape_EditTarget" in workbench.commands,
        "simulation workbench must register the drape target editor",
    )

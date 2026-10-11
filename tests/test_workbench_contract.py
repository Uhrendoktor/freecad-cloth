"""Behavioral checks for the package-owned Cloth workbenches."""

import importlib
from pathlib import Path

_WORKBENCHES = (
    ("freecad_cloth.pattern.workbench", "ClothPatternWorkbench", "Cloth Pattern"),
    ("freecad_cloth.sewing.workbench", "ClothSewingWorkbench", "Cloth Sewing"),
    ("freecad_cloth.simulation.workbench", "ClothSimulationWorkbench", "Cloth Simulation"),
)


def test_workbench_metadata_and_resources_are_runtime_objects():
    for module_name, class_name, menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        assert workbench.MenuText == menu
        assert workbench.ToolTip
        assert workbench.GetClassName() == "Gui::PythonWorkbench"
        assert Path(workbench.Icon).is_file()
        assert workbench.commands == []


def test_package_workbench_initializers_are_import_safe_and_unique():
    for module_name, class_name, _menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        workbench.Initialize()
        assert workbench.commands
        assert len(workbench.commands) == len(set(workbench.commands))


def test_simulation_workbench_registers_drape_and_simulation_surfaces():
    cls = getattr(importlib.import_module("freecad_cloth.simulation.workbench"), "ClothSimulationWorkbench")
    workbench = cls()
    workbench.Initialize()
    assert "ClothSimulation_CreateDrape" in workbench.commands
    assert "ClothSimulation_Step" in workbench.commands
    assert "ClothDrape_EditTarget" in workbench.commands

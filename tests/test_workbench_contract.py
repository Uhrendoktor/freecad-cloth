"""Contract checks for the package-owned Cloth workbenches."""

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_WORKBENCHES = (
    ("freecad_cloth.pattern.workbench", "ClothPatternWorkbench", "Cloth Pattern"),
    ("freecad_cloth.sewing.workbench", "ClothSewingWorkbench", "Cloth Sewing"),
    ("freecad_cloth.simulation.workbench", "ClothSimulationWorkbench", "Cloth Simulation"),
)


def test_registered_workbenches_have_stable_metadata():
    for module_name, class_name, menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        assert workbench.MenuText == menu
        assert workbench.ToolTip
        assert workbench.GetClassName() == "Gui::PythonWorkbench"
        assert Path(workbench.Icon).is_file()
        assert workbench.commands == []


def test_package_workbench_initializers_are_import_safe():
    for module_name, class_name, _menu in _WORKBENCHES:
        cls = getattr(importlib.import_module(module_name), class_name)
        workbench = cls()
        workbench.Initialize()
        assert workbench.commands
        assert len(workbench.commands) == len(set(workbench.commands))


def test_initgui_contains_only_loader_registration():
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    assert "Gui.addWorkbench(ClothPatternWorkbench())" in source
    assert "Gui.addWorkbench(ClothSimulationWorkbench())" in source
    assert "Gui.addWorkbench(ClothSewingWorkbench())" in source
    assert "from freecad_cloth." in source

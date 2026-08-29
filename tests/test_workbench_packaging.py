"""Headless checks for installable FreeCAD workbench registration."""
from pathlib import Path
import importlib.util
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def _load_init_gui():
    spec = importlib.util.spec_from_file_location("cloth_init_gui", ROOT / "InitGui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workbench_metadata_and_icons():
    module = _load_init_gui()
    workbenches = (
        module.ClothPatternWorkbench,
        module.ClothSimulationWorkbench,
        module.ClothSewingWorkbench,
    )
    names = {workbench.MenuText for workbench in workbenches}
    assert names == {"Cloth Pattern", "Cloth Simulation", "Cloth Sewing"}
    assert all(workbench.ToolTip for workbench in workbenches)
    assert all(workbench.GetClassName(None) == "Gui::PythonWorkbench" for workbench in workbenches)
    assert all(Path(workbench.Icon).is_file() for workbench in workbenches)


def test_workbench_command_groups_are_declared_once():
    module = _load_init_gui()
    assert len({module.ClothPatternWorkbench.Icon, module.ClothSimulationWorkbench.Icon, module.ClothSewingWorkbench.Icon}) == 3
    for workbench in (
        module.ClothPatternWorkbench(),
        module.ClothSimulationWorkbench(),
        module.ClothSewingWorkbench(),
    ):
        assert workbench.commands == ()


def test_addon_metadata_is_valid():
    root = ET.parse(ROOT / "package.xml").getroot()
    assert root.tag == "package"
    assert root.findtext("name") == "freecad-cloth"
    assert root.findtext("version")
    assert root.findtext("license")
    assert root.findtext("url") == "https://github.com/Uhrendoktor/freecad-cloth"

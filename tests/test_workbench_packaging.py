"""Headless checks for installable FreeCAD workbench registration."""

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"


def _load_init_gui():
    spec = importlib.util.spec_from_file_location("cloth_init_gui", ROOT / "InitGui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workbench_metadata_and_icons():
    module = _load_init_gui()
    workbenches = (
        module.ClothPatternWorkbench(),
        module.ClothSimulationWorkbench(),
        module.ClothSewingWorkbench(),
    )
    names = {workbench.MenuText for workbench in workbenches}
    assert names == {"Cloth Pattern", "Cloth Simulation", "Cloth Sewing"}
    assert all(workbench.ToolTip for workbench in workbenches)
    assert all(workbench.GetClassName() == "Gui::PythonWorkbench" for workbench in workbenches)
    assert all(
        (
            Path(workbench.Icon)
            if Path(workbench.Icon).is_absolute()
            else ICON_DIR / workbench.Icon
        ).is_file()
        for workbench in workbenches
    )


def test_workbench_command_groups_are_declared_once():
    module = _load_init_gui()
    workbenches = (
        module.ClothPatternWorkbench(),
        module.ClothSimulationWorkbench(),
        module.ClothSewingWorkbench(),
    )
    assert len({workbench.Icon for workbench in workbenches}) == 3
    for workbench in workbenches:
        assert workbench.commands == []


def test_addon_metadata_is_valid():
    root = ET.parse(ROOT / "package.xml").getroot()
    namespace = "{https://wiki.freecad.org/Package_Metadata}"
    assert root.tag == namespace + "package"
    assert root.findtext(namespace + "name") == "FreeCAD Cloth"
    assert root.findtext(namespace + "version") == "0.1.0"
    assert root.findtext(namespace + "license") == "LGPL-2.1-or-later"
    assert root.findtext(namespace + "url") == "https://github.com/Uhrendoktor/freecad-cloth"
    workbenches = root.find(namespace + "content")
    declared = {item.findtext(namespace + "classname") for item in workbenches.findall(namespace + "workbench")}
    assert declared == {"ClothPatternWorkbench", "ClothSewingWorkbench", "ClothSimulationWorkbench"}

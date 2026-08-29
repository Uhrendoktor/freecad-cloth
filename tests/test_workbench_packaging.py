"""Headless checks for installable FreeCAD workbench registration."""
from pathlib import Path
import importlib.util
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"


def _load_init_gui():
    spec = importlib.util.spec_from_file_location("cloth_init_gui", ROOT / "InitGui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _icon_path(workbench):
    """Resolve a FreeCAD icon resource the same way the package does.

    FreeCAD receives the icon basename after ``Gui.addIconPath`` registers the
    package icon directory.  A headless test running from the repository root
    cannot resolve that basename through FreeCAD's resource search path, so
    resolve it against the package's registered icon directory here.
    """
    icon = Path(workbench.Icon)
    return icon if icon.is_absolute() else ICON_DIR / icon


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
    assert all(_icon_path(workbench).is_file() for workbench in workbenches)


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

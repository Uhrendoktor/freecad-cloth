"""Headless regression checks for package-owned Cloth workbench registration."""

import importlib
from pathlib import Path

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import COMMAND_GROUPS as SEWING_COMMAND_GROUPS
from freecad_cloth.sewing.workbench import ClothSewingWorkbench
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"
EXPECTED_WORKBENCHES = {
    "Cloth Pattern": "Parametric sewing-pattern design",
    "Cloth Sewing": "Sewing operations and avatar fitting",
    "Cloth Simulation": "3D cloth assembly and simulation",
}


def test_workbench_resources_are_stable():
    workbenches = (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench())
    assert {wb.MenuText: wb.ToolTip for wb in workbenches} == EXPECTED_WORKBENCHES
    for wb in workbenches:
        resources = wb.GetResources()
        assert resources["MenuText"] == wb.MenuText
        assert resources["ToolTip"] == wb.ToolTip
        assert (
            Path(resources["Icon"]).resolve() == (ICON_DIR / Path(resources["Icon"]).name).resolve()
        )
        assert Path(resources["Icon"]).is_file()
        assert wb.GetClassName() == "Gui::PythonWorkbench"


def test_sewing_command_groups_are_unique_and_complete():
    commands = [command for _name, group in SEWING_COMMAND_GROUPS for command in group]
    assert commands
    assert len(commands) == len(set(commands))
    sewing = importlib.import_module("freecad_cloth.sewing.SewingCommands")
    network = importlib.import_module("freecad_cloth.sewing.SewingNetworkCommands")
    expected = set(sewing.COMMANDS + network.COMMANDS)
    assert set(commands) == expected


def test_initialize_is_idempotent_and_preserves_registered_command_order():
    for workbench in (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench()):
        workbench.Initialize()
        first = list(workbench.commands)
        assert first
        workbench.Initialize()
        assert workbench.commands == first
        assert len(workbench.commands) == len(set(workbench.commands))


def test_sewing_groups_cover_fitting_and_avatar_without_duplicates():
    wb = ClothSewingWorkbench()
    wb.Initialize()
    fitting = importlib.import_module("freecad_cloth.avatar.FittingCommands")
    avatar = importlib.import_module("freecad_cloth.avatar.AvatarCommands")
    assert set(wb.commands) == set(
        command for _name, group in SEWING_COMMAND_GROUPS for command in group
    ) | set(fitting.COMMANDS) | set(avatar.COMMANDS)

def test_workbench_package_metadata_matches_registration_surface():
    import xml.etree.ElementTree as ET

    root = ET.parse(ROOT / "package.xml").getroot()
    namespace = "{https://wiki.freecad.org/Package_Metadata}"
    assert root.tag == namespace + "package"
    assert root.findtext(namespace + "name") == "FreeCAD Cloth"
    assert root.findtext(namespace + "version") == "0.1.0"
    assert root.findtext(namespace + "license") == "LGPL-2.1-or-later"
    assert root.findtext(namespace + "url") == "https://github.com/Uhrendoktor/freecad-cloth"
    content = root.find(namespace + "content")
    declared = {
        item.findtext(namespace + "classname")
        for item in content.findall(namespace + "workbench")
    }
    assert declared == {
        "ClothPatternWorkbench",
        "ClothSewingWorkbench",
        "ClothSimulationWorkbench",
    }


def test_sewing_toolbar_is_stable_and_registered():
    from freecad_cloth.sewing.workbench import TOOLBAR_COMMANDS

    assert TOOLBAR_COMMANDS == (
        "ClothSewing_CreateSeam",
        "ClothSewing_CreateOperation",
        "ClothSewing_Validate",
    )
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    assert set(TOOLBAR_COMMANDS) <= set(workbench.commands)


def test_workbench_command_groups_do_not_overlap():
    import importlib

    groups = {
        "Pattern": {
            command
            for module_name in (
                "freecad_cloth.pattern.PatternCommands",
                "freecad_cloth.pattern.PatternMarks",
            )
            for command in importlib.import_module(module_name).COMMANDS
        },
        "Sewing": {
            command
            for module_name in (
                "freecad_cloth.sewing.SewingCommands",
                "freecad_cloth.sewing.SewingNetworkCommands",
                "freecad_cloth.avatar.FittingCommands",
                "freecad_cloth.avatar.AvatarCommands",
            )
            for command in importlib.import_module(module_name).COMMANDS
        },
        "Simulation": {
            command
            for module_name in (
                "freecad_cloth.simulation.SimulationCommands",
                "freecad_cloth.simulation.DrapeCommands",
            )
            for command in importlib.import_module(module_name).COMMANDS
        }
        | {"ClothRealtimePreview"},
    }
    seen = {}
    for workbench, commands in groups.items():
        assert commands
        for command in commands:
            assert command not in seen, (command, seen.get(command))
            seen[command] = workbench


def test_root_bootstrap_registers_exactly_the_three_package_workbenches():
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    assert source.count("Gui.addWorkbench(") == 3

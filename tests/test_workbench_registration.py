# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression checks for package-owned Cloth workbench registration."""

import importlib
import xml.etree.ElementTree as ET
from pathlib import Path

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import COMMAND_GROUPS as SEWING_COMMAND_GROUPS
from freecad_cloth.sewing.workbench import ClothSewingWorkbench
from freecad_cloth.sewing.workbench import TOOLBAR_COMMANDS
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"
EXPECTED_WORKBENCHES = {
    "Cloth Pattern": "Parametric sewing-pattern design",
    "Cloth Sewing": "Sewing operations and avatar fitting",
    "Cloth Simulation": "3D cloth assembly and simulation",
}


def _check(condition: object, message: str) -> None:
    """Raise a useful test failure when an explicit condition is false.

    Args:
        condition: Observed predicate that the test requires to be true.
        message: Explanation identifying the failed regression condition.

    Raises:
        AssertionError: If the supplied condition is false.
    """
    if not condition:
        raise AssertionError(message)


def test_workbench_resources_are_stable() -> None:
    """Verify the workbenches expose stable labels, tooltips, icons, and host class."""
    workbenches = (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench())
    _check(
        {wb.MenuText: wb.ToolTip for wb in workbenches} == EXPECTED_WORKBENCHES,
        "workbench menu labels and tooltips must remain stable",
    )
    for wb in workbenches:
        resources = wb.GetResources()
        _check(resources["MenuText"] == wb.MenuText, "resource menu text must match the workbench")
        _check(resources["ToolTip"] == wb.ToolTip, "resource tooltip must match the workbench")
        icon_path = Path(resources["Icon"])
        _check(
            icon_path.resolve() == (ICON_DIR / icon_path.name).resolve(),
            "workbench icon must resolve inside the canonical icon directory",
        )
        _check(icon_path.is_file(), "workbench icon file must exist")
        _check(wb.GetClassName() == "Gui::PythonWorkbench", "workbench host class must be stable")


def test_sewing_command_groups_are_unique_and_complete() -> None:
    """Verify sewing groups cover all sewing command identifiers without duplicates."""
    commands = [command for _name, group in SEWING_COMMAND_GROUPS for command in group]
    _check(bool(commands), "sewing command groups must not be empty")
    _check(len(commands) == len(set(commands)), "sewing command groups must be unique")
    sewing = importlib.import_module("freecad_cloth.sewing.SewingCommands")
    network = importlib.import_module("freecad_cloth.sewing.SewingNetworkCommands")
    expected = set(sewing.COMMANDS + network.COMMANDS)
    _check(set(commands) == expected, "sewing groups must cover both command modules")


def test_initialize_is_idempotent_and_preserves_registered_command_order() -> None:
    """Verify repeated initialization preserves each workbench command sequence."""
    for workbench in (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench()):
        workbench.Initialize()
        first = list(workbench.commands)
        _check(bool(first), "each workbench must register commands")
        workbench.Initialize()
        _check(workbench.commands == first, "reinitialization must preserve command order")
        _check(
            len(workbench.commands) == len(set(workbench.commands)),
            "reinitialization must not duplicate commands",
        )


def test_sewing_groups_cover_fitting_and_avatar_without_duplicates() -> None:
    """Verify sewing registration includes fitting and avatar commands exactly once."""
    wb = ClothSewingWorkbench()
    wb.Initialize()
    fitting = importlib.import_module("freecad_cloth.avatar.FittingCommands")
    avatar = importlib.import_module("freecad_cloth.avatar.AvatarCommands")
    expected = {
        command for _name, group in SEWING_COMMAND_GROUPS for command in group
    } | set(fitting.COMMANDS) | set(avatar.COMMANDS)
    _check(
        set(wb.commands) == expected,
        "sewing workbench must expose all fitting and avatar commands",
    )


def test_workbench_package_metadata_matches_registration_surface() -> None:
    """Verify package metadata names the same workbenches that the code registers."""
    root = ET.parse(ROOT / "package.xml").getroot()
    namespace = "{https://wiki.freecad.org/Package_Metadata}"
    _check(root.tag == namespace + "package", "package metadata root tag must match its namespace")
    _check(root.findtext(namespace + "name") == "FreeCAD Cloth", "package name must remain stable")
    _check(root.findtext(namespace + "version") == "0.1.0", "package version must remain stable")
    _check(
        root.findtext(namespace + "license") == "LGPL-2.1-or-later",
        "package license must remain stable",
    )
    _check(
        root.findtext(namespace + "url") == "https://github.com/Uhrendoktor/freecad-cloth",
        "package URL must identify the canonical repository",
    )
    content = root.find(namespace + "content")
    declared = {
        item.findtext(namespace + "classname")
        for item in content.findall(namespace + "workbench")
    }
    _check(
        declared
        == {
            "ClothPatternWorkbench",
            "ClothSewingWorkbench",
            "ClothSimulationWorkbench",
        },
        "package metadata must declare all registered workbenches",
    )


def test_sewing_toolbar_is_stable_and_registered() -> None:
    """Verify the canonical sewing toolbar remains ordered and registered."""

    _check(
        TOOLBAR_COMMANDS
        == (
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateOperation",
            "ClothSewing_Validate",
            "ClothFitting_CreateAvatar",
        ),
        "sewing toolbar command identifiers and order must remain stable",
    )
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    _check(
        set(TOOLBAR_COMMANDS) <= set(workbench.commands),
        "every toolbar command must be registered by the sewing workbench",
    )


def test_workbench_command_groups_do_not_overlap() -> None:
    """Verify pattern, sewing, and simulation command identifiers are disjoint."""
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
        } | {"ClothRealtimePreview"},
    }
    seen: dict[str, str] = {}
    for workbench, commands in groups.items():
        _check(bool(commands), f"{workbench} command group must not be empty")
        for command in commands:
            _check(command not in seen, f"{command!r} overlaps with {seen.get(command)!r}")
            seen[command] = workbench


def test_root_loader_delegates_registration_to_shared_bootstrap() -> None:
    """Verify InitGui delegates all workbench registration to the shared bootstrap."""
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    _check(
        "from freecad_cloth.bootstrap import initialize_workbenches" in source,
        "root GUI loader must import the shared bootstrap",
    )
    _check(
        source.count("initialize_workbenches(") == 1,
        "root GUI loader must bootstrap exactly once",
    )
    _check(
        "Gui.addWorkbench(" not in source,
        "root GUI loader must not duplicate workbench registration",
    )

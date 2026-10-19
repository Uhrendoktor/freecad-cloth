# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression checks for package-owned Cloth workbench registration."""

import importlib
from pathlib import Path

from defusedxml import ElementTree
import pytest

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import (
    COMMAND_GROUPS as SEWING_COMMAND_GROUPS,
    ClothSewingWorkbench,
    TOOLBAR_COMMANDS,
)
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"
EXPECTED_WORKBENCHES = {
    "Cloth Pattern": "Parametric sewing-pattern design",
    "Cloth Sewing": "Sewing operations and avatar fitting",
    "Cloth Simulation": "3D cloth assembly and simulation",
}


def _require(condition: object, message: str) -> None:
    """Raise a clear test failure when a workbench contract is violated.

    Args:
        condition: Predicate that must hold for the contract to pass.
        message: Human-readable reason to report when the predicate is false.

    Raises:
        AssertionError: When the expected condition does not hold.
    """
    if not condition:
        raise AssertionError(message)


def test_workbench_resources_are_stable() -> None:
    """Preserve workbench labels, tooltips, icon paths, and GUI class identity."""
    workbenches = (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench())
    _require(
        {workbench.MenuText: workbench.ToolTip for workbench in workbenches}
        == EXPECTED_WORKBENCHES,
        "Workbench menu metadata no longer matches the public registration contract.",
    )
    for workbench in workbenches:
        resources = workbench.GetResources()
        _require(
            resources["MenuText"] == workbench.MenuText,
            f"{workbench.MenuText} resources expose a mismatched menu label.",
        )
        _require(
            resources["ToolTip"] == workbench.ToolTip,
            f"{workbench.MenuText} resources expose a mismatched tooltip.",
        )
        icon = Path(resources["Icon"])
        _require(
            icon.resolve() == (ICON_DIR / icon.name).resolve(),
            f"{workbench.MenuText} resolves its icon outside the shared icon directory.",
        )
        _require(icon.is_file(), f"{workbench.MenuText} references a missing icon asset.")
        _require(
            workbench.GetClassName() == "Gui::PythonWorkbench",
            f"{workbench.MenuText} reports the wrong FreeCAD GUI workbench class.",
        )


def test_sewing_command_groups_are_unique_and_complete() -> None:
    """Ensure the sewing toolbar groups exactly cover the registered command modules."""
    commands = [command for _name, group in SEWING_COMMAND_GROUPS for command in group]
    _require(bool(commands), "Sewing command groups must not be empty.")
    _require(
        len(commands) == len(set(commands)),
        "Sewing command groups contain duplicate command identifiers.",
    )
    sewing = importlib.import_module("freecad_cloth.sewing.SewingCommands")
    network = importlib.import_module("freecad_cloth.sewing.SewingNetworkCommands")
    expected = set(sewing.COMMANDS + network.COMMANDS)
    _require(
        set(commands) == expected,
        "Sewing command groups do not match the commands exported by their modules.",
    )


def test_initialize_is_idempotent_and_preserves_registered_command_order() -> None:
    """Keep initialization repeatable without losing or duplicating commands."""
    for workbench in (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench()):
        workbench.Initialize()
        first = list(workbench.commands)
        _require(bool(first), f"{type(workbench).__name__} registered no commands.")
        workbench.Initialize()
        _require(
            workbench.commands == first,
            f"{type(workbench).__name__} changed command order during repeated initialization.",
        )
        _require(
            len(workbench.commands) == len(set(workbench.commands)),
            f"{type(workbench).__name__} registered duplicate command identifiers.",
        )


def test_sewing_groups_cover_fitting_and_avatar_without_duplicates() -> None:
    """Keep sewing registration complete for fitting and avatar commands."""
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    fitting = importlib.import_module("freecad_cloth.avatar.FittingCommands")
    avatar = importlib.import_module("freecad_cloth.avatar.AvatarCommands")
    expected = {
        command
        for _name, group in SEWING_COMMAND_GROUPS
        for command in group
    } | set(fitting.COMMANDS) | set(avatar.COMMANDS)
    _require(
        set(workbench.commands) == expected,
        "Sewing workbench commands differ from the sewing, fitting, and avatar registrations.",
    )


def test_workbench_package_metadata_matches_registration_surface() -> None:
    """Match package.xml metadata to the implemented workbench registration surface."""
    root = ElementTree.parse(ROOT / "package.xml").getroot()
    namespace = "{https://wiki.freecad.org/Package_Metadata}"
    _require(root.tag == namespace + "package", "Package metadata has an unexpected root tag.")
    _require(
        root.findtext(namespace + "name") == "FreeCAD Cloth",
        "Package metadata contains an unexpected package name.",
    )
    _require(
        root.findtext(namespace + "version") == "0.1.0",
        "Package metadata contains an unexpected version.",
    )
    _require(
        root.findtext(namespace + "license") == "LGPL-2.1-or-later",
        "Package metadata contains an unexpected license identifier.",
    )
    _require(
        root.findtext(namespace + "url") == "https://github.com/Uhrendoktor/freecad-cloth",
        "Package metadata contains an unexpected repository URL.",
    )
    content = root.find(namespace + "content")
    if content is None:
        pytest.fail("Package metadata does not declare any workbench content.")
    declared = {
        item.findtext(namespace + "classname")
        for item in content.findall(namespace + "workbench")
    }
    _require(
        declared
        == {
            "ClothPatternWorkbench",
            "ClothSewingWorkbench",
            "ClothSimulationWorkbench",
        },
        "Package metadata does not list exactly the implemented workbenches.",
    )


def test_sewing_toolbar_is_stable_and_registered() -> None:
    """Keep the public sewing toolbar command sequence registered and stable."""
    _require(
        TOOLBAR_COMMANDS
        == (
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateOperation",
            "ClothSewing_Validate",
            "ClothFitting_CreateAvatar",
        ),
        "Sewing toolbar command order no longer matches its public contract.",
    )
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    _require(
        set(TOOLBAR_COMMANDS) <= set(workbench.commands),
        "The sewing toolbar includes commands absent from workbench registration.",
    )


def test_workbench_command_groups_do_not_overlap() -> None:
    """Prevent command identifiers from colliding across registered workbenches."""
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
    seen: dict[str, str] = {}
    for workbench, commands in groups.items():
        _require(bool(commands), f"{workbench} workbench must expose at least one command.")
        for command in commands:
            _require(
                command not in seen,
                f"Command {command!r} occurs in both {workbench} and {seen.get(command)!r}.",
            )
            seen[command] = workbench


def test_root_loader_delegates_registration_to_shared_bootstrap() -> None:
    """Ensure the classic FreeCAD loader delegates workbench registration."""
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    _require(
        "from freecad_cloth.bootstrap import initialize_workbenches" in source,
        "The classic GUI loader must import the shared bootstrap registrar.",
    )
    _require(
        source.count("initialize_workbenches(") == 1,
        "The classic GUI loader must delegate registration exactly once.",
    )
    _require(
        "Gui.addWorkbench(" not in source,
        "The classic GUI loader must not duplicate bootstrap registration logic.",
    )

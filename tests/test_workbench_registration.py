# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression checks for package-owned Cloth workbench registration."""

import importlib
from pathlib import Path

from defusedxml import ElementTree
from freecad_cloth.avatar.CommandIds import AVATAR_COMMANDS, FITTING_COMMANDS

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import (
    COMMAND_GROUPS as SEWING_COMMAND_GROUPS,
)
from freecad_cloth.sewing.workbench import (
    TOOLBAR_COMMANDS,
    ClothSewingWorkbench,
)
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench
from tests.support.assertions import require as _require
from tests.support.assertions import require_not_none

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"
EXPECTED_WORKBENCHES = {
    "Cloth Pattern": "Parametric sewing-pattern design",
    "Cloth Sewing": "Sewing operations and avatar fitting",
    "Cloth Simulation": "3D cloth assembly and simulation",
}


def test_workbench_resources_are_stable() -> None:
    """Preserve workbench labels, tooltips, icon paths, and GUI class identity."""
    workbenches = (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench())
    _require(
        condition={workbench.MenuText: workbench.ToolTip for workbench in workbenches}
        == EXPECTED_WORKBENCHES,
        message="Workbench menu metadata no longer matches the public registration contract.",
    )
    for workbench in workbenches:
        resources = workbench.GetResources()
        _require(
            condition=resources["MenuText"] == workbench.MenuText,
            message=f"{workbench.MenuText} resources expose a mismatched menu label.",
        )
        _require(
            condition=resources["ToolTip"] == workbench.ToolTip,
            message=f"{workbench.MenuText} resources expose a mismatched tooltip.",
        )
        icon = Path(resources["Icon"])
        _require(
            condition=icon.resolve() == (ICON_DIR / icon.name).resolve(),
            message=f"{workbench.MenuText} resolves its icon outside the shared icon directory.",
        )
        _require(
            condition=icon.is_file(),
            message=f"{workbench.MenuText} references a missing icon asset.",
        )
        _require(
            condition=workbench.GetClassName() == "Gui::PythonWorkbench",
            message=f"{workbench.MenuText} reports the wrong FreeCAD GUI workbench class.",
        )


def test_sewing_command_groups_are_unique_and_complete() -> None:
    """Ensure the sewing toolbar groups exactly cover the registered command modules."""
    commands = [command for _name, group in SEWING_COMMAND_GROUPS for command in group]
    _require(condition=bool(commands), message="Sewing command groups must not be empty.")
    _require(
        condition=len(commands) == len(set(commands)),
        message="Sewing command groups contain duplicate command identifiers.",
    )
    sewing = importlib.import_module("freecad_cloth.sewing.SewingCommands")
    network = importlib.import_module("freecad_cloth.sewing.SewingNetworkCommands")
    expected = set(sewing.COMMANDS + network.COMMANDS)
    _require(
        condition=set(commands) == expected,
        message="Sewing command groups do not match the commands exported by their modules.",
    )


def test_initialize_is_idempotent_and_preserves_registered_command_order() -> None:
    """Keep initialization repeatable without losing or duplicating commands."""
    for workbench in (ClothPatternWorkbench(), ClothSewingWorkbench(), ClothSimulationWorkbench()):
        workbench.Initialize()
        first = list(workbench.commands)
        _require(
            condition=bool(first), message=f"{type(workbench).__name__} registered no commands."
        )
        workbench.Initialize()
        _require(
            condition=workbench.commands == first,
            message=f"{type(workbench).__name__} changed command order on repeat.",
        )
        _require(
            condition=len(workbench.commands) == len(set(workbench.commands)),
            message=f"{type(workbench).__name__} registered duplicate command identifiers.",
        )


def test_sewing_groups_cover_fitting_and_avatar_without_duplicates() -> None:
    """Keep sewing registration complete for fitting and avatar commands."""
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    expected = (
        {command for _name, group in SEWING_COMMAND_GROUPS for command in group}
        | set(FITTING_COMMANDS)
        | set(AVATAR_COMMANDS)
    )
    _require(
        condition=set(workbench.commands) == expected,
        message="Sewing workbench commands do not match the expected registration set.",
    )


def test_workbench_package_metadata_matches_registration_surface() -> None:
    """Match package.xml metadata to the implemented workbench registration surface."""
    root = require_not_none(
        ElementTree.parse(ROOT / "package.xml").getroot(),
        message="Package metadata did not parse to an XML root element.",
    )
    namespace = "{https://wiki.freecad.org/Package_Metadata}"
    _require(
        condition=root.tag == namespace + "package",
        message="Package metadata has an unexpected root tag.",
    )
    _require(
        condition=root.findtext(namespace + "name") == "FreeCAD Cloth",
        message="Package metadata contains an unexpected package name.",
    )
    _require(
        condition=root.findtext(namespace + "version") == "0.1.0",
        message="Package metadata contains an unexpected version.",
    )
    _require(
        condition=root.findtext(namespace + "license") == "LGPL-2.1-or-later",
        message="Package metadata contains an unexpected license identifier.",
    )
    _require(
        condition=root.findtext(namespace + "url")
        == "https://github.com/Uhrendoktor/freecad-cloth",
        message="Package metadata contains an unexpected repository URL.",
    )
    content = require_not_none(
        root.find(namespace + "content"),
        message="Package metadata does not declare any workbench content.",
    )
    declared = {
        item.findtext(namespace + "classname") for item in content.findall(namespace + "workbench")
    }
    _require(
        condition=declared
        == {
            "ClothPatternWorkbench",
            "ClothSewingWorkbench",
            "ClothSimulationWorkbench",
        },
        message="Package metadata does not list exactly the implemented workbenches.",
    )


def test_sewing_toolbar_is_stable_and_registered() -> None:
    """Keep the public sewing toolbar command sequence registered and stable."""
    _require(
        condition=TOOLBAR_COMMANDS
        == (
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateOperation",
            "ClothSewing_Validate",
            "ClothFitting_CreateAvatar",
        ),
        message="Sewing toolbar command order no longer matches its public contract.",
    )
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    _require(
        condition=set(TOOLBAR_COMMANDS) <= set(workbench.commands),
        message="The sewing toolbar includes commands absent from workbench registration.",
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
        _require(
            condition=bool(commands),
            message=f"{workbench} workbench must expose at least one command.",
        )
        for command in commands:
            _require(
                condition=command not in seen,
                message=f"Duplicate command {command!r}: {workbench!r} and {seen.get(command)!r}.",
            )
            seen[command] = workbench


def test_root_loader_delegates_registration_to_shared_bootstrap() -> None:
    """Ensure the classic FreeCAD loader delegates workbench registration."""
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    _require(
        condition="from freecad_cloth.bootstrap import initialize_workbenches" in source,
        message="The classic GUI loader must import the shared bootstrap registrar.",
    )
    _require(
        condition=source.count("initialize_workbenches(") == 1,
        message="The classic GUI loader must delegate registration exactly once.",
    )
    _require(
        condition="Gui.addWorkbench(" not in source,
        message="The classic GUI loader must not duplicate bootstrap registration logic.",
    )

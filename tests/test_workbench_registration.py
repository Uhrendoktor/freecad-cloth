"""Headless regression checks for package-owned Cloth workbench registration."""
import importlib

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import COMMAND_GROUPS as SEWING_COMMAND_GROUPS, ClothSewingWorkbench
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench


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
        assert resources["Icon"] in {"ClothPattern.svg", "ClothSewing.svg", "ClothSimulation.svg"}
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
    fitting = importlib.import_module("freecad_cloth.simulation.FittingCommands")
    avatar = importlib.import_module("freecad_cloth.avatar.AvatarCommands")
    assert set(wb.commands) == set(
        command
        for _name, group in SEWING_COMMAND_GROUPS
        for command in group
    ) | set(fitting.COMMANDS) | set(avatar.COMMANDS)

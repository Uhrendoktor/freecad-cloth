"""Headless regression checks for native Cloth workbench registration."""
import importlib

import InitGui


EXPECTED_WORKBENCHES = {
    "Cloth Pattern": "Parametric sewing-pattern design",
    "Cloth Sewing": "Sewing operations and avatar fitting",
    "Cloth Simulation": "3D cloth assembly and simulation",
}


def test_workbench_resources_are_stable():
    workbenches = (
        InitGui.ClothPatternWorkbench(),
        InitGui.ClothSewingWorkbench(),
        InitGui.ClothSimulationWorkbench(),
    )
    assert {wb.MenuText: wb.ToolTip for wb in workbenches} == EXPECTED_WORKBENCHES
    for wb in workbenches:
        resources = wb.GetResources()
        assert resources["MenuText"] == wb.MenuText
        assert resources["ToolTip"] == wb.ToolTip
        assert resources["Icon"] == {
            "Cloth Pattern": "ClothPattern.svg",
            "Cloth Sewing": "ClothSewing.svg",
            "Cloth Simulation": "ClothSimulation.svg",
        }[wb.MenuText]
        assert wb.GetClassName() == "Gui::PythonWorkbench"


def test_sewing_command_groups_are_unique_and_complete():
    groups = InitGui.SEWING_COMMAND_GROUPS
    commands = [command for _name, group in groups for command in group]
    assert commands
    assert len(commands) == len(set(commands))

    sewing = importlib.import_module("SewingCommands")
    network = importlib.import_module("SewingNetworkCommands")
    expected = set(sewing.COMMANDS + network.COMMANDS)
    assert set(commands) == expected


def test_initialize_is_idempotent_and_preserves_registered_command_order():
    for workbench in (
        InitGui.ClothPatternWorkbench(),
        InitGui.ClothSewingWorkbench(),
        InitGui.ClothSimulationWorkbench(),
    ):
        workbench.Initialize()
        first = list(workbench.commands)
        assert first
        workbench.Initialize()
        assert workbench.commands == first
        assert len(workbench.commands) == len(set(workbench.commands))


def test_sewing_groups_cover_fitting_and_avatar_without_duplicates():
    # Keep this contract tied to the actual command declarations, rather than
    # duplicating the complete list in the test.
    wb = InitGui.ClothSewingWorkbench()
    wb.Initialize()
    fitting = importlib.import_module("FittingCommands")
    avatar = importlib.import_module("AvatarCommands")
    assert set(wb.commands) == set(
        command
        for _name, group in InitGui.SEWING_COMMAND_GROUPS
        for command in group
    ) | set(fitting.COMMANDS) | set(avatar.COMMANDS)

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


def test_sewing_menu_groups_have_stable_workflow_order_and_names():
    assert [name for name, _commands in InitGui.SEWING_COMMAND_GROUPS] == [
        "Sewing Creation",
        "Sewing Editing",
        "Validation & View",
    ]
    for name, commands in InitGui.SEWING_COMMAND_GROUPS:
        assert name
        assert commands
        assert list(commands) == list(dict.fromkeys(commands))


def test_sewing_toolbar_is_a_stable_small_subset_of_registered_commands():
    sewing = importlib.import_module("SewingCommands")
    network = importlib.import_module("SewingNetworkCommands")
    fitting = importlib.import_module("FittingCommands")
    avatar = importlib.import_module("AvatarCommands")
    all_commands = set(sewing.COMMANDS + network.COMMANDS + fitting.COMMANDS + avatar.COMMANDS)

    assert InitGui.SEWING_TOOLBAR_COMMANDS == (
        "ClothSewing_CreateSeam",
        "ClothSewing_CreateOperation",
        "ClothSewing_Validate",
    )
    assert set(InitGui.SEWING_TOOLBAR_COMMANDS) <= all_commands
    assert len(InitGui.SEWING_TOOLBAR_COMMANDS) == len(set(InitGui.SEWING_TOOLBAR_COMMANDS))


def test_sewing_group_validator_rejects_duplicate_or_missing_commands():
    expected = ("A", "B")
    assert InitGui._validate_sewing_command_groups(
        (("One", ("A",)), ("Two", ("B",))), expected
    ) is None

    try:
        InitGui._validate_sewing_command_groups(
            (("One", ("A", "A")), ("Two", ("B",))), expected
        )
    except ValueError as exc:
        assert "duplicates" in str(exc)
    else:
        raise AssertionError("duplicate command groups must be rejected")

    try:
        InitGui._validate_sewing_command_groups(
            (("One", ("A",)), ("Two", ("C",))), expected
        )
    except ValueError as exc:
        assert "out of sync" in str(exc)
        assert "missing: B" in str(exc)
        assert "unexpected: C" in str(exc)
    else:
        raise AssertionError("out-of-sync command groups must be rejected")

"""Regression checks for the package-owned Cloth workbench registration."""

from pathlib import Path

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import COMMAND_GROUPS, TOOLBAR_COMMANDS, ClothSewingWorkbench
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

ROOT = Path(__file__).resolve().parents[1]


def _commands(module_names):
    commands = set()
    import importlib
    for name in module_names:
        commands.update(importlib.import_module(name).COMMANDS)
    return commands


def test_sewing_menu_groups_have_stable_names_order_and_complete_commands():
    expected = _commands((
        "freecad_cloth.sewing.SewingCommands",
        "freecad_cloth.sewing.SewingNetworkCommands",
    ))
    grouped = [command for _name, commands in COMMAND_GROUPS[:3] for command in commands]
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == expected


def test_fitting_and_avatar_form_final_sewing_group():
    fitting = _commands(("freecad_cloth.avatar.FittingCommands", "freecad_cloth.avatar.AvatarCommands"))
    assert COMMAND_GROUPS[-1] == ("Fitting & Avatar", ())
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    assert fitting <= set(workbench.commands)


def test_sewing_toolbar_is_stable_and_subset_of_registered_commands():
    assert TOOLBAR_COMMANDS == ("ClothSewing_CreateSeam", "ClothSewing_CreateOperation", "ClothSewing_Validate")
    workbench = ClothSewingWorkbench()
    workbench.Initialize()
    assert set(TOOLBAR_COMMANDS) <= set(workbench.commands)


def test_workbench_command_groups_do_not_overlap():
    groups = {
        "Pattern": _commands(("freecad_cloth.pattern.PatternCommands", "freecad_cloth.pattern.PatternMarks")),
        "Sewing": _commands(("freecad_cloth.sewing.SewingCommands", "freecad_cloth.sewing.SewingNetworkCommands", "freecad_cloth.avatar.FittingCommands", "freecad_cloth.avatar.AvatarCommands")),
        "Simulation": _commands(("freecad_cloth.simulation.SimulationCommands", "freecad_cloth.simulation.DrapeCommands")) | {"ClothRealtimePreview"},
    }
    seen = {}
    for workbench, commands in groups.items():
        assert commands
        for command in commands:
            previous = seen.setdefault(command, workbench)
            assert previous == workbench, (command, previous, workbench)


def test_bootstrap_is_only_the_root_registration_surface():
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    assert source.count("Gui.addWorkbench(") == 3

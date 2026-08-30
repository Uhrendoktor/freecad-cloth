"""Static checks for the real FreeCAD GUI layer."""
from pathlib import Path

from InitGui import SEWING_COMMAND_GROUPS, SEWING_TOOLBAR_COMMANDS, ClothSewingWorkbench

ROOT = Path(__file__).resolve().parents[1]
init_gui = (ROOT / "InitGui.py").read_text()
pattern_gui = (ROOT / "PatternGui.py").read_text()
sim_gui = (ROOT / "SimulationGui.py").read_text()
sewing_gui = (ROOT / "SewingGui.py").read_text()
commands = (ROOT / "PatternCommands.py").read_text()
sim_commands = (ROOT / "SimulationCommands.py").read_text()
sewing_commands = (ROOT / "SewingCommands.py").read_text()

assert "Gui.addWorkbench(ClothPatternWorkbench())" in init_gui
assert "Gui.addWorkbench(ClothSimulationWorkbench())" in init_gui
assert "Gui.addWorkbench(ClothSewingWorkbench())" in init_gui
assert 'MenuText = "Cloth Sewing"' in init_gui
assert 'def GetResources(self):' in init_gui
assert '"MenuText": self.MenuText' in init_gui
assert '"ToolTip": self.ToolTip' in init_gui
assert '"Icon": self.Icon' in init_gui
assert "def __init__(self):" in init_gui
assert "self.commands = []" in init_gui
assert "if self.commands:" in init_gui
assert "command not in registered" in init_gui
assert 'return "Gui::PythonWorkbench"' in init_gui
assert "class PatternPieceTaskPanel" in pattern_gui
assert "Gui.Control.showDialog(panel)" in pattern_gui
assert "class SimulationTaskPanel" in sim_gui
assert "Gui.Control.showDialog(panel)" in sim_gui
assert "class SewingTaskPanel" in sewing_gui
assert "Gui.Control.showDialog(panel)" in sewing_gui
assert "ClothPattern_CreatePieceTask" in commands
assert "ClothPattern_EditPiece" in commands
assert "ClothPattern_Show2D" in commands
assert "ClothSimulation_Edit" in sim_commands
assert "ClothSewing_CreateOperation" in sewing_commands
assert "ClothSewing_EditOperation" in sewing_commands
assert "ClothSewing_Validate" in sewing_commands


def test_sewing_command_groups_are_unique_and_complete():
    groups = dict(SEWING_COMMAND_GROUPS)
    assert tuple(groups) == ("Sewing Creation", "Sewing Editing", "Validation & View")
    commands = [command for group in groups.values() for command in group]
    assert len(commands) == len(set(commands))
    assert set(commands) == {
        "ClothSewing_CreateSeam",
        "ClothSewing_CreateMNSewing",
        "ClothSewing_CreateNetwork",
        "ClothSewing_FreeSewing",
        "ClothSewing_CreateOperation",
        "ClothSewing_EditOperation",
        "ClothSewing_EditNetwork",
        "ClothSewing_ReverseSeam",
        "ClothSewing_ToggleAlignment",
        "ClothSewing_Validate",
        "ClothSewing_RepairSeam",
        "ClothSewing_Show2D",
    }


def test_sewing_command_group_validator_rejects_missing_or_duplicate_commands():
    expected = ["one", "two", "three"]
    from InitGui import _validate_sewing_command_groups

    _validate_sewing_command_groups((("A", ("one",)), ("B", ("two", "three"))), expected)
    try:
        _validate_sewing_command_groups((("A", ("one",)), ("B", ("two",))), expected)
    except ValueError as exc:
        assert "missing: three" in str(exc)
    else:
        raise AssertionError("missing command group entry was not rejected")
    try:
        _validate_sewing_command_groups((("A", ("one", "two")), ("B", ("two", "three"))), expected)
    except ValueError as exc:
        assert "duplicates" in str(exc)
    else:
        raise AssertionError("duplicate command group entry was not rejected")


def test_workbench_group_registration_is_idempotent_and_keeps_flat_context_commands():
    workbench = ClothSewingWorkbench()
    calls = []
    workbench.appendToolbar = lambda name, commands: calls.append(("toolbar", name, list(commands)))
    workbench.appendMenu = lambda name, commands: calls.append(("menu", name, list(commands)))
    workbench._register_groups(SEWING_COMMAND_GROUPS, toolbar_name=workbench.MenuText)
    first_calls = list(calls)
    workbench._register_groups(SEWING_COMMAND_GROUPS, toolbar_name=workbench.MenuText)
    assert calls == first_calls
    assert workbench.commands == [
        command for _group, commands in SEWING_COMMAND_GROUPS for command in commands
    ]
    assert [kind for kind, _name, _commands in calls] == [
        "toolbar", "menu", "menu", "menu"
    ]
    assert calls[0][1] == "Cloth Sewing"
    assert calls[0][2] == workbench.commands
    assert calls[1][1] == ["Cloth Sewing", "Sewing Creation"]
    assert calls[2][1] == ["Cloth Sewing", "Sewing Editing"]
    assert calls[3][1] == ["Cloth Sewing", "Validation & View"]


def test_sewing_workbench_initialize_registers_fitting_group_and_preserves_toolbar_contract():
    import AvatarCommands
    import FittingCommands

    workbench = ClothSewingWorkbench()
    calls = []
    workbench.appendToolbar = lambda name, commands: calls.append(("toolbar", name, list(commands)))
    workbench.appendMenu = lambda name, commands: calls.append(("menu", name, list(commands)))

    workbench.Initialize()

    assert calls[0] == ("toolbar", "Cloth Sewing", list(SEWING_TOOLBAR_COMMANDS))
    fitting = next(commands for kind, name, commands in calls if kind == "menu" and name == ["Cloth Sewing", "Fitting & Avatar"])
    assert fitting == list(FittingCommands.COMMANDS + AvatarCommands.COMMANDS)
    assert workbench.commands == [
        command
        for group in SEWING_COMMAND_GROUPS
        for command in group[1]
    ] + list(FittingCommands.COMMANDS + AvatarCommands.COMMANDS)
    assert len(workbench.commands) == len(set(workbench.commands))


def test_workbench_icons_are_present_and_valid_svg_resources():
    for name in ("ClothPattern.svg", "ClothSimulation.svg", "ClothSewing.svg"):
        path = ROOT / "resources" / "icons" / name
        assert path.is_file(), path
        content = path.read_text(encoding="utf-8").lstrip()
        assert content.startswith("<svg "), path
        assert "xmlns=\"http://www.w3.org/2000/svg\"" in content

print("GUI structure checks passed")

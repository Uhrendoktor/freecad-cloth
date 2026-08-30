"""Static checks for the real FreeCAD GUI layer."""
from pathlib import Path

from InitGui import SEWING_COMMAND_GROUPS, ClothSewingWorkbench

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

print("GUI structure checks passed")

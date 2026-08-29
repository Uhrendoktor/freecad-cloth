"""Static checks for the real FreeCAD GUI layer."""
from pathlib import Path

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

print("GUI structure checks passed")

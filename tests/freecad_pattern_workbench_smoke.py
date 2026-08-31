"""FreeCAD GUI smoke test for the Cloth Pattern Design workbench."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import FreeCAD as App
import FreeCADGui as Gui
import InitGui
from PatternCommands import create_pattern_piece
from PatternGui import PatternPieceTaskPanel, PatternDraftingTaskPanel


def main():
    workbench = InitGui.ClothPatternWorkbench()
    Gui.activateWorkbench("Cloth Pattern")
    workbench.Initialize()
    assert workbench.MenuText == "Cloth Pattern"
    assert "ClothPattern_CreatePieceTask" in workbench.commands
    assert "ClothPattern_CreateDrafting" in workbench.commands

    doc = App.newDocument("PatternWorkbenchSmoke")
    piece = create_pattern_piece()
    doc.recompute()
    assert piece.PatternType == "PatternPiece"
    assert piece.Shape.isValid()
    assert piece.Sketch is not None
    assert piece.Sketch.TypeId == "Sketcher::SketchObject"
    assert piece.Sketch.GeometryAuthority == "Sketcher"

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    from PatternCommands import edit_sketch
    sketch = edit_sketch()
    assert sketch is piece.Sketch
    assert Gui.activeDocument().getInEdit() == piece.Sketch.Name
    Gui.activeDocument().resetEdit()

    panel = PatternPieceTaskPanel(piece)
    panel.name.setText("Smoke Piece")
    panel.width.setValue(140.0)
    panel.height.setValue(80.0)
    panel.allowance.setValue(6.0)
    assert panel.accept() is True
    assert piece.Label == "Smoke Piece"
    assert abs(float(piece.Width) - 140.0) < 1e-9
    assert abs(float(piece.Height) - 80.0) < 1e-9
    assert abs(float(piece.SeamAllowance) - 6.0) < 1e-9
    assert piece.Shape.isValid()

    original = piece.DraftingBoundary
    drafting = PatternDraftingTaskPanel(piece)
    drafting.nudge(10.0, 0.0)
    assert drafting.obj.DraftingBoundary != original
    assert drafting.reject() is True
    assert piece.DraftingBoundary == original
    assert piece.Shape.isValid()

    Gui.Control.closeDialog()
    App.closeDocument(doc.Name)
    print("Pattern Design workbench/task-panel smoke test passed")


if __name__ == "__main__":
    main()

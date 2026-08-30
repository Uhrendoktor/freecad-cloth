"""Real FreeCAD smoke test for sewing task-panel lifecycle and semantic persistence."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import FreeCAD as App
import FreeCADGui as Gui

from PatternCommands import create_pattern_piece_from_parameters
from PatternModel import Seam
from PatternObjects import add_seam
from SewingObjects import add_sewing_operation
from SewingGui import SewingTaskPanel


def main():
    # Exercise the public workbench activation path before document operations.
    Gui.activateWorkbench("Cloth Sewing")
    assert Gui.activeWorkbench() == "Cloth Sewing", "Cloth Sewing workbench did not activate"

    doc = App.newDocument("ClothSewingSmoke")
    try:
        piece_a = create_pattern_piece_from_parameters("PieceA", 100, 60, 0, 0)
        piece_b = create_pattern_piece_from_parameters("PieceB", 100, 60, 0, 0)
        seam_model = Seam(piece_a.PieceId, 0, piece_b.PieceId, 0, id="smoke-seam")
        seam = add_seam(doc, seam_model)
        operation = add_sewing_operation(doc, seam, piece_a, piece_b)
        doc.recompute()

        assert str(seam.EdgeAId) == f"{piece_a.PieceId}:edge:0"
        assert str(seam.EdgeBId) == f"{piece_b.PieceId}:edge:0"
        assert str(seam.EdgeASignature) and str(seam.EdgeBSignature)
        assert str(seam.Status) == "Valid"
        assert seam.PatternA is piece_a and seam.PatternB is piece_b

        panel = SewingTaskPanel(operation)
        buttons = panel.getStandardButtons()
        assert buttons != 0
        original = (
            float(operation.Tolerance),
            int(operation.Stitches),
            str(seam.Alignment),
            bool(seam.ReversedB),
        )

        panel.tolerance.setValue(3.0)
        panel.stitches.setValue(20)
        panel.alignment.setCurrentText("uniform")
        panel.reversed_b.setChecked(True)
        panel.reject()
        assert (
            float(operation.Tolerance),
            int(operation.Stitches),
            str(seam.Alignment),
            bool(seam.ReversedB),
        ) == original
        assert operation.StitchCount == original[1]

        panel = SewingTaskPanel(operation)
        panel.tolerance.setValue(1.75)
        panel.stitches.setValue(16)
        panel.alignment.setCurrentText("uniform")
        panel.reversed_b.setChecked(True)
        assert panel.accept() is True
        assert abs(float(operation.Tolerance) - 1.75) < 1e-9
        assert int(operation.Stitches) == 16
        assert int(operation.StitchCount) == 16
        assert str(seam.Alignment) == "uniform"
        assert bool(seam.ReversedB) is True
        assert str(operation.Alignment) == "uniform"
        assert bool(operation.ReversedB) is True
        assert operation.Status == "Valid"
        assert len(operation.StitchPoints) == 16

        # Accepted task-panel edits must form one native FreeCAD undo step.
        if hasattr(doc, "undo") and hasattr(doc, "redo"):
            doc.undo()
            assert abs(float(operation.Tolerance) - original[0]) < 1e-9
            assert int(operation.Stitches) == original[1]
            assert str(seam.Alignment) == original[2]
            assert bool(seam.ReversedB) == original[3]
            doc.redo()
            assert abs(float(operation.Tolerance) - 1.75) < 1e-9
            assert int(operation.Stitches) == 16
            assert str(seam.Alignment) == "uniform"
            assert bool(seam.ReversedB) is True
            assert operation.Status == "Valid"

        piece_a.Width = 120
        doc.recompute()
        assert str(seam.EdgeAId) == f"{piece_a.PieceId}:edge:0"
        assert str(seam.Status) == "Changed reference"
        assert str(seam.EdgeASignature) != ""
        assert operation.Status != "Valid"

        piece_a.Width = 100
        doc.recompute()
        assert str(seam.Status) == "Valid"
        assert operation.Status == "Valid"

        fd, path = tempfile.mkstemp(suffix=".FCStd")
        os.close(fd)
        try:
            doc.recompute()
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            reloaded = App.openDocument(path)
            reloaded.recompute()
            restored = reloaded.getObject(operation.Name)
            restored_seam = reloaded.getObject(seam.Name)
            assert restored is not None
            assert restored.SewingType == "SewingOperation"
            assert abs(float(restored.Tolerance) - 1.75) < 1e-9
            assert int(restored.Stitches) == 16
            assert int(restored.StitchCount) == 16
            assert str(restored.Alignment) == "uniform"
            assert bool(restored.ReversedB) is True
            assert str(restored_seam.Alignment) == "uniform"
            assert bool(restored_seam.ReversedB) is True
            assert str(restored_seam.EdgeAId).endswith(":edge:0")
            assert str(restored_seam.EdgeBId).endswith(":edge:0")
            assert str(restored_seam.Status) == "Valid"
            assert restored.Status == "Valid"
            assert len(restored.StitchPoints) == 16
            assert restored.Seam is not None
            assert restored.PieceA is not None and restored.PieceB is not None
            print("FreeCAD sewing task transaction, semantic persistence, invalidation, and workbench activation smoke test passed", flush=True)
        finally:
            if App.ActiveDocument is not None:
                App.closeDocument(App.ActiveDocument.Name)
            try:
                os.unlink(path)
            except OSError:
                pass
    finally:
        if App.ActiveDocument is not None:
            App.closeDocument(App.ActiveDocument.Name)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)

"""Real FreeCAD smoke test for sewing task-panel lifecycle and persistence."""
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
    doc = App.newDocument("ClothSewingSmoke")
    try:
        piece_a = create_pattern_piece_from_parameters("PieceA", 100, 60, 0, 0)
        piece_b = create_pattern_piece_from_parameters("PieceB", 100, 60, 0, 0)
        seam_model = Seam(piece_a.PieceId, 0, piece_b.PieceId, 0, id="smoke-seam")
        seam = add_seam(doc, seam_model)
        operation = add_sewing_operation(doc, seam, piece_a, piece_b)
        doc.recompute()

        panel = SewingTaskPanel(operation)
        buttons = panel.getStandardButtons()
        assert buttons != 0
        original = (float(operation.Tolerance), int(operation.Stitches))

        # update() must pull external document changes into the visible controls.
        operation.Tolerance = 2.25
        operation.Stitches = 12
        doc.recompute()
        panel.update()
        assert abs(panel.tolerance.value() - 2.25) < 1e-9
        assert panel.stitches.value() == 12
        operation.Tolerance, operation.Stitches = original
        doc.recompute()
        panel.update()
        assert abs(panel.tolerance.value() - original[0]) < 1e-9
        assert panel.stitches.value() == original[1]

        # Cancel restores the document values and recomputes the operation.
        panel.tolerance.setValue(3.0)
        panel.stitches.setValue(20)
        panel.reject()
        assert (float(operation.Tolerance), int(operation.Stitches)) == original
        assert operation.StitchCount == original[1]

        # Accept commits the edited values and leaves the recomputed result.
        panel = SewingTaskPanel(operation)
        panel.tolerance.setValue(1.75)
        panel.stitches.setValue(16)
        assert panel.accept() is True
        assert abs(float(operation.Tolerance) - 1.75) < 1e-9
        assert int(operation.Stitches) == 16
        assert int(operation.StitchCount) == 16
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
            assert restored is not None
            assert restored.SewingType == "SewingOperation"
            assert abs(float(restored.Tolerance) - 1.75) < 1e-9
            assert int(restored.Stitches) == 16
            assert int(restored.StitchCount) == 16
            assert restored.Status == "Valid"
            assert restored.Seam is not None
            assert restored.PieceA is not None and restored.PieceB is not None
            print("FreeCAD sewing task-panel lifecycle and save/reload smoke test passed")
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

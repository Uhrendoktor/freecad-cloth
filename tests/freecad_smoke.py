"""Headless smoke test executed by freecadcmd in CI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import FreeCAD as App

from PatternCommands import create_pattern_piece


def main():
    doc = App.newDocument("ClothSmoke")
    create_pattern_piece()
    obj = doc.getObject("PatternPiece")
    assert obj is not None
    assert obj.PieceId == "pattern-piece-1"
    assert obj.SewingBoundary == "bottom,right,top,left"
    assert obj.Shape.isValid()
    initial = obj.Shape.BoundBox.XLength
    obj.Width = 120
    doc.recompute()
    assert obj.Shape.isValid()
    assert obj.Shape.BoundBox.XLength != initial
    assert obj.PieceId == "pattern-piece-1"
    print("FreeCAD document smoke test passed")


if __name__ == "__main__":
    main()

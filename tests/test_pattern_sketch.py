import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from PatternSketch import create_sketch_for_piece


def test_pattern_sketch_module_is_headless_safe():
    piece = PatternPiece("Front", [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)], id="front")
    piece.validate()
    assert [f"{piece.id}:edge:{i}" for i in range(4)] == ["front:edge:0", "front:edge:1", "front:edge:2", "front:edge:3"]


def test_pattern_sketch_requires_freecad_when_called():
    piece = PatternPiece("Front", [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0)], id="front")
    if "FreeCAD" in sys.modules:
        return
    try:
        create_sketch_for_piece(piece)
    except RuntimeError as exc:
        assert "FreeCAD Sketcher" in str(exc)
    else:
        raise AssertionError("headless environment should not create a native Sketcher object")

"""Headless regression coverage for native Pattern workbench commands."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import PatternCommands


def test_one_step_pattern_piece_command_is_registered():
    assert "ClothPattern_CreatePieceWithSketch" in PatternCommands.COMMANDS


def test_one_step_pattern_piece_command_creates_native_sketch(monkeypatch):
    class Document:
        def __init__(self):
            self.recompute_calls = 0

        def recompute(self):
            self.recompute_calls += 1

    document = Document()
    piece = type(
        "PatternPieceObject",
        (),
        {
            "Label": "Bodice",
            "PieceId": "pattern-piece-1",
            "SeamAllowance": 8.0,
            "GrainlineAngle": 0.0,
            "SewingOutline": "[(0, 0), (100, 0), (100, 60), (0, 60)]",
        },
    )()
    calls = []

    monkeypatch.setattr(PatternCommands, "create_pattern_piece", lambda: piece)
    monkeypatch.setitem(sys.modules, "FreeCAD", type("FreeCAD", (), {"ActiveDocument": document}))

    class PatternPiece:
        def __init__(self, name, points, **kwargs):
            self.name = name
            self.outline = points
            self.kwargs = kwargs

    def create_sketch_for_piece(model, doc):
        calls.append((model, doc))
        return "Sketch"

    monkeypatch.setitem(sys.modules, "PatternModel", type("PatternModel", (), {"PatternPiece": PatternPiece}))
    monkeypatch.setitem(sys.modules, "PatternSketch", type("PatternSketch", (), {"create_sketch_for_piece": create_sketch_for_piece}))

    result = PatternCommands.create_pattern_piece_with_sketch()

    assert result is piece
    assert len(calls) == 1
    model, doc = calls[0]
    assert model.name == "Bodice"
    assert model.outline == [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)]
    assert model.kwargs == {
        "seam_allowance": 8.0,
        "grainline_angle": 0.0,
        "id": "pattern-piece-1",
    }
    assert doc is document
    assert document.recompute_calls == 1

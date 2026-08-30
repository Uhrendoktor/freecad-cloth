import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from PatternSketch import create_sketch_for_piece
from PatternDrafting import parse_points, serialize_points, add_point, remove_point, bounds
from PatternValidation import validate_piece


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


def test_one_step_pattern_piece_command_is_registered_and_creates_native_sketch():
    import PatternCommands

    class Document:
        def __init__(self):
            self.recompute_calls = 0

        def recompute(self):
            self.recompute_calls += 1

    document = Document()
    piece = type("PatternPieceObject", (), {
        "Label": "Bodice",
        "PieceId": "pattern-piece-1",
        "SeamAllowance": 8.0,
        "GrainlineAngle": 0.0,
        "SewingOutline": "[(0, 0), (100, 0), (100, 60), (0, 60)]",
    })()
    calls = []
    original_create = PatternCommands.create_pattern_piece
    old_freecad = sys.modules.get("FreeCAD")
    old_sketch = sys.modules.get("PatternSketch")

    PatternCommands.create_pattern_piece = lambda: piece
    sys.modules["FreeCAD"] = type("FreeCAD", (), {"ActiveDocument": document})

    def create_sketch_for_piece(model, doc):
        calls.append((model, doc))
        return "Sketch"

    sys.modules["PatternSketch"] = type("PatternSketch", (), {"create_sketch_for_piece": create_sketch_for_piece})
    try:
        assert "ClothPattern_CreatePieceWithSketch" in PatternCommands.COMMANDS
        result = PatternCommands.create_pattern_piece_with_sketch()
    finally:
        PatternCommands.create_pattern_piece = original_create
        if old_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = old_freecad
        if old_sketch is None:
            sys.modules.pop("PatternSketch", None)
        else:
            sys.modules["PatternSketch"] = old_sketch

    assert result is piece
    assert len(calls) == 1
    model, doc = calls[0]
    assert model.name == "Bodice"
    assert model.outline == [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)]
    assert model.seam_allowance == 8.0
    assert model.grainline_angle == 0.0
    assert model.id == "pattern-piece-1"
    assert doc is document
    assert document.recompute_calls == 1


def test_polygon_drafting_round_trip_and_editing():
    points = ((0.0, 0.0), (80.0, 0.0), (100.0, 40.0), (40.0, 70.0), (0.0, 50.0))
    encoded = serialize_points(points)
    assert parse_points(encoded) == points
    edited = add_point(points, 90.0, 20.0, 2)
    assert len(edited) == 6
    edited = remove_point(edited, 2)
    assert edited == points
    assert bounds(points) == (0.0, 0.0, 100.0, 70.0)


class _Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Line:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _Sketch:
    def __init__(self, geometry):
        self.Geometry = geometry


class _PieceObject:
    Label = "Front"
    PieceId = "front"
    GeometryAuthority = "Sketcher"
    SeamAllowance = 8.0
    GrainlineAngle = 0.0

    def __init__(self, geometry):
        self.Sketch = _Sketch(geometry)
        self.PropertiesList = []

    def addProperty(self, kind, name, group):
        self.PropertiesList.append(name)
        setattr(self, name, "Unknown" if kind.endswith("Enumeration") else "")
        return self


def test_closed_native_boundary_validation_persists_measurement():
    piece = _PieceObject([
        _Line((100, 60), (0, 60)), _Line((0, 0), (100, 0)),
        _Line((0, 60), (0, 0)), _Line((100, 0), (100, 60)),
    ])
    result = validate_piece(piece)
    assert result["valid"] is True
    assert result["edge_count"] == 4
    assert abs(result["perimeter"] - 320.0) < 1e-9
    assert piece.ValidationStatus == "Valid"


def test_open_native_boundary_validation_is_persistently_invalid():
    piece = _PieceObject([
        _Line((0, 0), (100, 0)), _Line((100, 0), (100, 60)),
        _Line((100, 60), (0, 60)),
    ])
    result = validate_piece(piece)
    assert result["valid"] is False
    assert piece.ValidationStatus == "Invalid"
    assert "open" in piece.ValidationMessage.lower()


if __name__ == "__main__":
    test_pattern_sketch_module_is_headless_safe()
    test_pattern_sketch_requires_freecad_when_called()
    test_one_step_pattern_piece_command_is_registered_and_creates_native_sketch()
    test_polygon_drafting_round_trip_and_editing()
    test_closed_native_boundary_validation_persists_measurement()
    test_open_native_boundary_validation_is_persistently_invalid()
    print("pattern sketch tests passed")

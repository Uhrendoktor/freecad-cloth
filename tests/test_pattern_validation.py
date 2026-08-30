import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternValidation import validate_piece


class Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class LineSegment:
    def __init__(self, start, end):
        self.StartPoint = Point(*start)
        self.EndPoint = Point(*end)


class Sketch:
    def __init__(self, geometry):
        self.Geometry = geometry


class Piece:
    Label = "Front"
    PieceId = "front"
    GeometryAuthority = "Sketcher"
    SeamAllowance = 8.0
    GrainlineAngle = 0.0
    PropertiesList = []

    def __init__(self, geometry):
        self.Sketch = Sketch(geometry)
        self._values = {}
        self.PropertiesList = []

    def addProperty(self, kind, name, group):
        self.PropertiesList.append(name)
        setattr(self, name, "Unknown" if kind.endswith("Enumeration") else "")
        return self


def test_closed_sketch_is_valid_and_persisted():
    piece = Piece([
        LineSegment((100, 60), (0, 60)),
        LineSegment((0, 0), (100, 0)),
        LineSegment((0, 60), (0, 0)),
        LineSegment((100, 0), (100, 60)),
    ])
    result = validate_piece(piece)
    assert result["valid"] is True
    assert result["edge_count"] == 4
    assert piece.ValidationStatus == "Valid"
    assert "perimeter" in piece.ValidationMessage


def test_open_sketch_is_invalid_and_reports_reason():
    piece = Piece([
        LineSegment((0, 0), (100, 0)),
        LineSegment((100, 0), (100, 60)),
        LineSegment((100, 60), (0, 60)),
    ])
    result = validate_piece(piece)
    assert result["valid"] is False
    assert piece.ValidationStatus == "Invalid"
    assert "open" in piece.ValidationMessage.lower()


if __name__ == "__main__":
    test_closed_sketch_is_valid_and_persisted()
    test_open_sketch_is_invalid_and_reports_reason()
    print("pattern validation tests passed")

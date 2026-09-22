import math

from freecad_cloth.common.PatternSimulationAdapter import resolve_simulation_pattern


class Point:
    def __init__(self, x, y):
        self.x, self.y, self.z = float(x), float(y), 0.0


class Line:
    def __init__(self, start, end):
        self.StartPoint = Point(*start)
        self.EndPoint = Point(*end)


class Arc:
    FirstParameter = 0.0
    LastParameter = math.pi

    def valueAt(self, parameter):
        t = float(parameter) / math.pi
        return Point(10.0 + math.sin(math.pi * t), 10.0 * t)


class Sketch:
    Geometry = [Line((0, 0), (10, 0)), Arc(), Line((10, 10), (0, 10)), Line((0, 10), (0, 0))]
    SemanticEdgeIds = ("piece:edge:0", "piece:edge:1", "piece:edge:2", "piece:edge:3")

    def getConstruction(self, _index):
        return False


class Piece:
    PatternType = "PatternPiece"
    GeometryAuthority = "Sketcher"
    Placement = None
    SeamAllowance = 0.0
    GrainlineAngle = 0.0
    Width = 10.0
    Height = 10.0

    def __init__(self):
        self.PieceId = "piece"
        self.Name = "Piece"
        self.Label = "Piece"
        self.Sketch = Sketch()

    @property
    def SewingOutline(self):
        raise AssertionError("Sketch-authoritative adapter touched legacy outline")

    @property
    def DraftingBoundary(self):
        raise AssertionError("Sketch-authoritative adapter touched legacy boundary")


class Doc:
    def __init__(self, piece):
        self.Objects = [piece]


def test_sketch_geometry_resolves_to_pattern_ir():
    piece = Piece()
    resolved = resolve_simulation_pattern(Doc(piece), [piece], curve_samples=11)
    boundaries = resolved.pattern.piece("piece").boundaries
    assert [boundary.id for boundary in boundaries] == list(Piece().Sketch.SemanticEdgeIds)
    assert boundaries[1].kind == "arc"
    assert len(boundaries[1].samples) == 11


if __name__ == "__main__":
    test_sketch_geometry_resolves_to_pattern_ir()
    print("Pattern simulation adapter tests passed")

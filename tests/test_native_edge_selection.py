from types import SimpleNamespace

from freecad_cloth.pattern.PatternObjects import _seam_edge_id
from freecad_cloth.pattern.PatternIR import PatternIR


class Point:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


class Line:
    def __init__(self, start, end):
        self.StartPoint = Point(*start)
        self.EndPoint = Point(*end)


class Sketch:
    def __init__(self):
        pts = [(0, 0), (10, 0), (10, 8), (8, 10), (2, 10), (0, 8), (0, 10), (-2, 8)]
        self.Geometry = [Line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        self.SemanticEdgeIds = [f"front:edge:{i}" for i in range(len(pts))]

    def getConstruction(self, _index):
        return False


def test_native_edge_number_maps_through_sketch_semantic_ids_after_ir_reordering():
    sketch = Sketch()
    assert PatternIR._sketch_boundaries
    piece = SimpleNamespace(
        PieceId="front",
        Label="front",
        Width=12.0,
        Height=10.0,
        SeamAllowance=0.0,
        GrainlineAngle=0.0,
        GeometryAuthority="Sketcher",
        GeometryMode="Sketch",
        Sketch=sketch,
        DraftingBoundary=repr([(0, 0), (10, 0), (10, 8), (8, 10), (2, 10), (0, 8), (0, 10), (-2, 8)]),
    )
    semantic_id, _ = _seam_edge_id(piece, 1, "A")
    assert semantic_id == "front:edge:1"

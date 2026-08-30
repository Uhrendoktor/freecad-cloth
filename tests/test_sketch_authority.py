import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from PatternIR import PatternIR
from SeamGraph import SeamGraph
from SketcherPatternContract import configure_authority, ensure_semantic_edge_ids


class Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class LineSegment:
    def __init__(self, start, end):
        self.StartPoint = Point(*start)
        self.EndPoint = Point(*end)


class FakeSketch:
    def __init__(self, geometry=(), ids=()):
        self.Geometry = list(geometry)
        self.SemanticEdgeIds = list(ids)
        self.PropertiesList = []

    def addProperty(self, _kind, name, _group):
        self.PropertiesList.append(name)


def test_pattern_ir_accepts_fake_sketcher_lines_in_shuffled_insertion_order():
    piece = PatternPiece("Front", [(0, 0), (100, 0), (100, 60), (0, 60)], id="front")
    graph = SeamGraph(); graph.add_piece(piece)
    class Sketch:
        Geometry = [
            LineSegment((100, 60), (0, 60)),
            LineSegment((0, 0), (100, 0)),
            LineSegment((0, 60), (0, 0)),
            LineSegment((100, 0), (100, 60)),
        ]
    result = PatternIR.from_sketches(graph, {"front": Sketch()})
    boundaries = result.piece("front").boundaries
    assert len(boundaries) == 4
    assert boundaries[0].id == "front:edge:0"
    assert all(boundary.kind == "line" for boundary in boundaries)
    for current, following in zip(boundaries, boundaries[1:] + boundaries[:1]):
        assert current.samples[-1] == following.samples[0]


def test_sketch_contract_assigns_ids_only_for_appended_geometry():
    sketch = FakeSketch([LineSegment((0, 0), (10, 0))], ["front:edge:0"])
    assert ensure_semantic_edge_ids(sketch, "front") == ("front:edge:0",)
    sketch.Geometry.append(LineSegment((10, 0), (10, 10)))
    assert ensure_semantic_edge_ids(sketch, "front") == ("front:edge:0", "front:edge:1")


def test_sketch_contract_rejects_geometry_deletion_instead_of_retargeting():
    sketch = FakeSketch(
        [LineSegment((0, 0), (10, 0)), LineSegment((10, 0), (10, 10))],
        ["front:edge:0", "front:edge:1"],
    )
    sketch.Geometry.pop(0)
    try:
        ensure_semantic_edge_ids(sketch, "front")
    except ValueError as exc:
        assert "topology changed by deletion" in str(exc)
    else:
        raise AssertionError("deleted Sketcher geometry must invalidate semantic mapping")


def test_sketch_contract_persists_authority_metadata():
    sketch = FakeSketch([], [])
    configure_authority(sketch, "front")
    assert sketch.PatternPieceId == "front"
    assert sketch.GeometryAuthority == "Sketcher"
    assert sketch.GeometryContractVersion == "1"
    assert sketch.GeometrySource == "ClothPattern.PatternPiece"


if __name__ == "__main__":
    test_pattern_ir_accepts_fake_sketcher_lines_in_shuffled_insertion_order()
    test_sketch_contract_assigns_ids_only_for_appended_geometry()
    test_sketch_contract_rejects_geometry_deletion_instead_of_retargeting()
    test_sketch_contract_persists_authority_metadata()
    print("sketch authority adapter tests passed")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternIR import PatternIR
from SeamGraph import SeamGraph


class Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class LineSegment:
    def __init__(self, start, end):
        self.StartPoint = Point(*start)
        self.EndPoint = Point(*end)


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


if __name__ == "__main__":
    test_pattern_ir_accepts_fake_sketcher_lines_in_shuffled_insertion_order()
    print("sketch authority adapter tests passed")

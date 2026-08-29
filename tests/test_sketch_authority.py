import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from PatternIR import PatternIR
from SeamGraph import SeamGraph


class Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class LineSegment:
    __name__ = "LineSegment"
    __module__ = "Part"
    def __init__(self, start, end):
        self.StartPoint = Point(*start)
        self.EndPoint = Point(*end)


def test_pattern_ir_accepts_fake_sketcher_lines_in_topological_order():
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
    assert [b.samples[0][:2] for b in result.piece("front").boundaries] == [
        (0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)
    ]
    assert all(boundary.kind == "line" for boundary in result.piece("front").boundaries)


if __name__ == "__main__":
    test_pattern_ir_accepts_fake_sketcher_lines_in_topological_order()
    print("sketch authority adapter tests passed")

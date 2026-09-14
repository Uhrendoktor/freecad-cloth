import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternIR import PatternIR
from freecad_cloth.sewing.SeamGraph import SeamGraph


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


def test_pattern_ir_accepts_single_closed_native_curve_as_a_pattern_boundary():
    piece = PatternPiece("Circle", [(0, 0), (100, 0), (100, 100)], id="circle")
    graph = SeamGraph(); graph.add_piece(piece)

    class Circle:
        FirstParameter = 0.0
        LastParameter = 2.0 * math.pi

        def valueAt(self, parameter):
            return Point(50.0 + 50.0 * math.cos(parameter), 50.0 + 50.0 * math.sin(parameter))

    class Sketch:
        Geometry = [Circle()]

    result = PatternIR.from_sketches(graph, {"circle": Sketch()}, curve_samples=32)
    boundary = result.piece("circle").boundaries[0]
    assert boundary.kind == "curve"
    assert len(boundary.samples) == 32
    assert boundary.samples[0] == boundary.samples[-1]


def test_pattern_ir_rejects_open_single_curve_as_a_pattern_boundary():
    piece = PatternPiece("Open", [(0, 0), (100, 0), (100, 100)], id="open")
    graph = SeamGraph(); graph.add_piece(piece)

    class Curve:
        FirstParameter = 0.0
        LastParameter = 1.0

        def valueAt(self, parameter):
            return Point(100.0 * parameter, 40.0 * parameter)

    class Sketch:
        Geometry = [Curve()]

    try:
        PatternIR.from_sketches(graph, {"open": Sketch()})
    except ValueError as exc:
        assert "single boundary does not close" in str(exc)
    else:
        raise AssertionError("an open single Sketcher curve must not be a cloth pattern")


if __name__ == "__main__":
    test_pattern_ir_accepts_fake_sketcher_lines_in_shuffled_insertion_order()
    test_pattern_ir_accepts_single_closed_native_curve_as_a_pattern_boundary()
    test_pattern_ir_rejects_open_single_curve_as_a_pattern_boundary()
    print("sketch authority adapter tests passed")

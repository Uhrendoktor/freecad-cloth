import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from PatternIR import PatternIR
from PatternModel import PatternPiece, Seam
from SeamGraph import SeamGraph


def _graph():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (20, 0), (20, 20), (0, 20)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (20, 0), (20, 20), (0, 20)], id="back"))
    graph.add_seam(Seam("front", 1, "back", "edge:3", id="side", reversed_b=True, alignment="uniform"))
    return graph


def test_integer_and_string_edges_become_semantic_ids():
    ir = PatternIR.from_graph(_graph())
    seam = ir.seams[0]
    assert seam.edge_a == "edge:1"
    assert seam.edge_b == "edge:3"
    assert seam.reversed_b is True
    assert seam.alignment == "uniform"
    ir.validate()


def test_richer_curve_geometry_survives_in_the_ir():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    graph.add_seam(Seam("front", "curve", "back", "bottom", id="curve-seam"))
    geometry = {
        "front": ParametricPattern([
            QuadraticBezier("curve", (0, 0), (5, 8), (10, 0)),
            LineSegment("line-a", (10, 0), (0, 10)),
            LineSegment("line-b", (0, 10), (0, 0)),
        ]),
        "back": rectangle(10, 10),
    }
    ir = PatternIR.from_graph(graph, geometry, curve_samples=9)
    boundary = ir.boundary("front", "curve")
    assert boundary.kind == "curve"
    assert len(boundary.samples) == 9
    assert boundary.samples[0] == (0.0, 0.0, 0.0)
    assert boundary.samples[-1] == (10.0, 0.0, 0.0)
    assert boundary.length > 10.0


class _Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class NativeLineSegment:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _NativeCurve:
    FirstParameter = 2.0
    LastParameter = 4.0

    def __init__(self, start, end):
        self._start = start
        self._end = end

    def valueAt(self, parameter):
        t = (parameter - self.FirstParameter) / (self.LastParameter - self.FirstParameter)
        return _Point(
            self._start[0] + (self._end[0] - self._start[0]) * t,
            self._start[1] + (self._end[1] - self._start[1]) * t,
        )


class ArcOfCircle(_NativeCurve):
    pass


class BSplineCurve(_NativeCurve):
    pass


class BezierCurve(_NativeCurve):
    pass


class _Sketch:
    def __init__(self, geometry, semantic_ids):
        self.Geometry = geometry
        self.SemanticEdgeIds = semantic_ids

    def getConstruction(self, index):
        return False


def _sketch_graph(curve, edge_id):
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    graph.add_seam(Seam("piece", edge_id, "other", "other:edge:0", id="seam"))
    geometry = [
        NativeLineSegment((0, 0), (10, 0)),
        curve,
        NativeLineSegment((10, 10), (0, 10)),
        NativeLineSegment((0, 10), (0, 0)),
    ]
    return graph, _Sketch(geometry, ["piece:edge:0", edge_id, "piece:edge:2", "piece:edge:3"])


def _other_sketch():
    return _Sketch([
        NativeLineSegment((0, 0), (10, 0)),
        NativeLineSegment((10, 0), (10, 10)),
        NativeLineSegment((10, 10), (0, 10)),
        NativeLineSegment((0, 10), (0, 0)),
    ], ["other:edge:0", "other:edge:1", "other:edge:2", "other:edge:3"])


def test_native_sketch_curve_kinds_are_preserved():
    for native_type, expected_kind in ((ArcOfCircle, "arc"), (BSplineCurve, "bspline"), (BezierCurve, "bezier")):
        curve = native_type((10, 0), (10, 10))
        graph, sketch = _sketch_graph(curve, "piece:curved")
        ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()}, curve_samples=7)
        boundary = ir.boundary("piece", "piece:curved")
        assert boundary.kind == expected_kind
        assert boundary.parameter_range == (2.0, 4.0)
        assert len(boundary.samples) == 7
        assert boundary.samples[0] == (10.0, 0.0, 0.0)
        assert boundary.samples[-1] == (10.0, 10.0, 0.0)


def test_sketch_semantic_ids_survive_raw_integer_seam_resolution():
    curve = ArcOfCircle((10, 0), (10, 10))
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    graph.add_seam(Seam("piece", 1, "other", 0, id="seam"))
    sketch = _Sketch([
        NativeLineSegment((0, 0), (10, 0)), curve,
        NativeLineSegment((10, 10), (0, 10)), NativeLineSegment((0, 10), (0, 0))
    ], ["piece:edge:0", "piece:curve", "piece:edge:2", "piece:edge:3"])
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    assert ir.seams[0].edge_a == "piece:curve"
    assert ir.boundary("piece", "piece:curve").kind == "arc"


def test_unresolvable_string_reference_fails_closed():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    try:
        graph.add_seam(Seam("front", "missing", "back", 0, id="bad"))
    except ValueError:
        return
    raise AssertionError("invalid seam reference was accepted")


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("PatternIR tests passed")

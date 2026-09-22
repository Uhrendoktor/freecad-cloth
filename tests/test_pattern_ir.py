import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import LineSegment as GeometryLineSegment, ParametricPattern, QuadraticBezier, rectangle
from freecad_cloth.pattern.PatternIR import PatternIR
from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.sewing.SeamGraph import SeamGraph
from freecad_cloth.sewing.SeamReference import ChangedEdgeReference, capture_edge_reference, resolve_edge_reference, resolve_edge_reference_status


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
            GeometryLineSegment("line-a", (10, 0), (0, 10)),
            GeometryLineSegment("line-b", (0, 10), (0, 0)),
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


class LineSegment:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _NativeCurve:
    FirstParameter = 2.0
    LastParameter = 4.0

    def __init__(self, start, end, bend=0.0):
        self._start = start
        self._end = end
        self._bend = float(bend)

    def valueAt(self, parameter):
        t = (parameter - self.FirstParameter) / (self.LastParameter - self.FirstParameter)
        x = self._start[0] + (self._end[0] - self._start[0]) * t
        y = self._start[1] + (self._end[1] - self._start[1]) * t
        dx = self._end[0] - self._start[0]
        dy = self._end[1] - self._start[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length > 1e-12:
            import math
            offset = self._bend * math.sin(math.pi * t) / length
            x += -dy * offset
            y += dx * offset
        return _Point(x, y)


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
        LineSegment((0, 0), (10, 0)),
        curve,
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 10), (0, 0)),
    ]
    return graph, _Sketch(geometry, ["piece:edge:0", edge_id, "piece:edge:2", "piece:edge:3"])


def _other_sketch():
    return _Sketch([
        LineSegment((0, 0), (10, 0)),
        LineSegment((10, 0), (10, 10)),
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 10), (0, 0)),
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


def test_native_bezier_boundary_uses_physical_arc_length_not_endpoint_chord():
    graph, sketch = _sketch_graph(BezierCurve((10, 0), (10, 10), bend=8.0), "piece:bezier")
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()}, curve_samples=17)
    boundary = ir.boundary("piece", "piece:bezier")
    chord = ((boundary.samples[-1][0] - boundary.samples[0][0]) ** 2 + (boundary.samples[-1][1] - boundary.samples[0][1]) ** 2) ** 0.5
    assert boundary.kind == "bezier"
    assert boundary.length > chord


def _pattern_ir_edge_record(boundary):
    samples = tuple(tuple(point) for point in boundary.samples)
    return {
        "piece_id": "piece",
        "id": boundary.id,
        "points": (
            (samples[0][0], samples[0][1]),
            (samples[-1][0], samples[-1][1]),
        ),
        "provenance": (
            "PatternIR",
            "Sketcher",
            boundary.kind,
            boundary.parameter_range,
            samples,
        ),
    }


def test_native_curve_shape_change_with_same_endpoints_is_changed_reference():
    first_curve = ArcOfCircle((10, 0), (10, 10), bend=4.0)
    second_curve = ArcOfCircle((10, 0), (10, 10), bend=7.0)
    first_graph, first_sketch = _sketch_graph(first_curve, "piece:curved")
    second_graph, second_sketch = _sketch_graph(second_curve, "piece:curved")
    first_ir = PatternIR.from_sketches(first_graph, {"piece": first_sketch, "other": _other_sketch()}, curve_samples=9)
    second_ir = PatternIR.from_sketches(second_graph, {"piece": second_sketch, "other": _other_sketch()}, curve_samples=9)
    first_edge = _pattern_ir_edge_record(first_ir.boundary("piece", "piece:curved"))
    second_edge = _pattern_ir_edge_record(second_ir.boundary("piece", "piece:curved"))
    assert first_edge["points"] == second_edge["points"]
    assert first_edge["provenance"] != second_edge["provenance"]
    reference = capture_edge_reference("piece", first_edge["id"], first_edge["points"], first_edge["provenance"])
    try:
        resolve_edge_reference(reference, [second_edge])
    except ChangedEdgeReference:
        pass
    else:
        raise AssertionError("native curve shape change must be a Changed reference")
    assert resolve_edge_reference_status(reference, [second_edge]) == (False, "changed")


def test_legacy_endpoint_reference_remains_valid_against_native_provenance():
    curve = ArcOfCircle((10, 0), (10, 10), bend=7.0)
    graph, sketch = _sketch_graph(curve, "piece:curved")
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()}, curve_samples=9)
    current = _pattern_ir_edge_record(ir.boundary("piece", "piece:curved"))
    legacy = capture_edge_reference("piece", current["id"], current["points"])
    assert resolve_edge_reference_status(legacy, [current]) == (True, "valid")


def test_shuffled_sketch_geometry_resolves_by_endpoint_connectivity():
    curve = ArcOfCircle((10, 0), (10, 10))
    graph, _ = _sketch_graph(curve, "piece:curve")
    shuffled = _Sketch([
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 0), (10, 0)),
        curve,
        LineSegment((0, 10), (0, 0)),
    ], ["piece:edge:2", "piece:edge:0", "piece:curve", "piece:edge:3"])
    ir = PatternIR.from_sketches(graph, {"piece": shuffled, "other": _other_sketch()})
    assert [edge.id for edge in ir.pieces[0].boundaries] == [
        "piece:curve", "piece:edge:2", "piece:edge:3", "piece:edge:0"
    ]
    assert ir.seams[0].edge_a == "piece:curve"
    assert ir.boundary("piece", "piece:edge:2").samples[0] == (10.0, 10.0, 0.0)


def test_shuffled_line_sketch_geometry_is_deterministic():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch([
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 10), (0, 0)),
        LineSegment((0, 0), (10, 0)),
        LineSegment((10, 0), (10, 10)),
    ], ["piece:edge:2", "piece:edge:3", "piece:edge:0", "piece:edge:1"])
    graph.add_seam(Seam("piece", 1, "other", 0, id="seam"))
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    assert [edge.id for edge in ir.pieces[0].boundaries] == [
        "piece:edge:0", "piece:edge:3", "piece:edge:2", "piece:edge:1"
    ]
    assert ir.seams[0].edge_a == "piece:edge:3"


def test_open_sketch_boundary_fails_with_diagnostic():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch([
        LineSegment((0, 0), (10, 0)),
        LineSegment((10, 0), (10, 10)),
        LineSegment((10, 10), (0, 10)),
    ], ["piece:edge:0", "piece:edge:1", "piece:edge:2"])
    try:
        PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    except ValueError as exc:
        assert "open" in str(exc)
        return
    raise AssertionError("open Sketcher boundary was accepted")


def test_ambiguous_sketch_boundary_fails_with_diagnostic():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch([
        LineSegment((0, 0), (10, 0)),
        LineSegment((10, 0), (10, 10)),
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 10), (0, 0)),
        LineSegment((0, 0), (10, 10)),
    ], [
        "piece:edge:0", "piece:edge:1", "piece:edge:2", "piece:edge:3", "piece:diagonal"
    ])
    try:
        PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    except ValueError as exc:
        assert "ambiguous" in str(exc)
        return
    raise AssertionError("ambiguous Sketcher boundary was accepted")


def test_disconnected_sketch_boundaries_fail_with_diagnostic():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch([
        LineSegment((0, 0), (1, 0)),
        LineSegment((1, 0), (0.5, 1)),
        LineSegment((0.5, 1), (0, 0)),
        LineSegment((20, 0), (21, 0)),
        LineSegment((21, 0), (20.5, 1)),
        LineSegment((20.5, 1), (20, 0)),
    ], [
        "piece:a", "piece:b", "piece:c", "piece:d", "piece:e", "piece:f"
    ])
    try:
        PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    except ValueError as exc:
        assert "disconnected" in str(exc)
        return
    raise AssertionError("disconnected Sketcher boundaries were accepted")


def test_sketch_semantic_ids_survive_raw_integer_seam_resolution():
    curve = ArcOfCircle((10, 0), (10, 10))
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    graph.add_seam(Seam("piece", 1, "other", 0, id="seam"))
    sketch = _Sketch([
        LineSegment((0, 0), (10, 0)), curve,
        LineSegment((10, 10), (0, 10)), LineSegment((0, 10), (0, 0))
    ], ["piece:edge:0", "piece:curve", "piece:edge:2", "piece:edge:3"])
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    assert ir.seams[0].edge_a == "piece:curve"
    assert ir.boundary("piece", "piece:curve").kind == "arc"


def test_unresolvable_string_reference_fails_closed():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    graph.add_seam(Seam("front", "missing", "back", 0, id="bad"))
    try:
        PatternIR.from_graph(graph)
    except ValueError:
        return
    raise AssertionError("invalid seam reference was accepted")


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("PatternIR tests passed")

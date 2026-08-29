import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from PatternIR import PatternIR
from PatternMesh import triangulate
from PatternModel import PatternPiece, Seam
from SewingConstraints import build_sewing_constraints
from SeamGraph import SeamGraph


def test_rectangle_mesh_area_and_topology():
    pattern = rectangle(100.0, 50.0)
    mesh = triangulate(pattern)
    assert len(mesh.vertices) == 4
    assert len(mesh.triangles) == 2
    assert abs(mesh.area - 5000.0) < 1e-7
    assert mesh.boundary_edge_segment_ids == ("bottom", "right", "top", "left")
    mesh.validate()


def test_concave_polygon_triangulates():
    pattern = ParametricPattern([
        LineSegment("a", (0, 0), (40, 0)),
        LineSegment("b", (40, 0), (40, 40)),
        LineSegment("c", (40, 40), (20, 20)),
        LineSegment("d", (20, 20), (0, 40)),
        LineSegment("e", (0, 40), (0, 0)),
    ])
    mesh = triangulate(pattern)
    assert len(mesh.triangles) == 3
    assert abs(mesh.area - 1200.0) < 1e-7
    assert mesh.boundary_edge_segment_ids == ("a", "b", "c", "d", "e")


def test_reversed_rectangle_retains_segment_provenance():
    pattern = ParametricPattern([
        LineSegment("left", (0, 50), (0, 0)),
        LineSegment("bottom", (0, 0), (100, 0)),
        LineSegment("right", (100, 0), (100, 50)),
        LineSegment("top", (100, 50), (0, 50)),
    ])
    mesh = triangulate(pattern)
    assert mesh.boundary_edge_segment_ids == ("left", "bottom", "right", "top")


def test_seam_generates_stitches():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    constraints = build_sewing_constraints(a, ma, b, mb, Seam("front", 1, "back", 3, id="side"), samples=5)
    assert len(constraints.stitches) >= 2
    constraints.validate()


def test_pattern_ir_normalizes_raw_seam_indices_to_semantic_ids():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (10, 10), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (10, 10), (0, 10)], id="back"))
    graph.add_seam(Seam("front", 1, "back", 3, id="side"))
    ir = PatternIR.from_graph(graph)
    assert (ir.seams[0].edge_a, ir.seams[0].edge_b) == ("edge:1", "edge:3")
    assert ir.boundary("front", "edge:1").kind == "line"


def test_pattern_ir_keeps_curve_provenance_outside_solver_types():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    graph.add_seam(Seam("front", "curve", "back", "line", id="curve-seam"))
    geometry = {
        "front": ParametricPattern([
            # A curve remains a curve in the IR; it is not flattened into
            # a solver-specific or FreeCAD-specific object.
            QuadraticBezier("curve", (0, 0), (5, 8), (10, 0)),
            LineSegment("line-a", (10, 0), (0, 10)),
            LineSegment("line-b", (0, 10), (0, 0)),
        ]),
        "back": rectangle(10, 10),
    }
    ir = PatternIR.from_graph(graph, geometry, curve_samples=9)
    assert ir.boundary("front", "curve").kind == "curve"
    assert len(ir.boundary("front", "curve").samples) == 9


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("mesh tests passed")

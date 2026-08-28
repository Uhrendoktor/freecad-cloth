import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternGeometry import LineSegment, ParametricPattern, rectangle
from PatternMesh import triangulate
from PatternModel import Seam
from SewingConstraints import build_sewing_constraints


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
    assert mesh.boundary_edge_segment_ids == ("top", "right", "bottom", "left")


def test_seam_generates_stitches():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    constraints = build_sewing_constraints(a, ma, b, mb, Seam("front", 1, "back", 3, id="side"), samples=5)
    assert len(constraints.stitches) >= 2
    constraints.validate()


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("mesh tests passed")

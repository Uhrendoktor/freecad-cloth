import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, rectangle
from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingConstraints import build_sewing_constraints


def test_rectangle_mesh_area_and_topology():
    pattern = rectangle(100.0, 50.0)
    mesh = triangulate(pattern)
    assert len(mesh.vertices) == 4
    assert len(mesh.triangles) == 2
    assert abs(mesh.area - 5000.0) < 1e-7
    assert mesh.boundary_edge_segment_ids == ("bottom", "right", "top", "left")
    mesh.validate()


def test_concave_polygon_triangulates():
    pattern = ParametricPattern(
        [
            LineSegment("a", (0, 0), (40, 0)),
            LineSegment("b", (40, 0), (40, 40)),
            LineSegment("c", (40, 40), (20, 20)),
            LineSegment("d", (20, 20), (0, 40)),
            LineSegment("e", (0, 40), (0, 0)),
        ]
    )
    mesh = triangulate(pattern)
    assert len(mesh.triangles) == 3
    assert abs(mesh.area - 1200.0) < 1e-7
    assert mesh.boundary_edge_segment_ids == ("a", "b", "c", "d", "e")


def test_reversed_rectangle_retains_segment_provenance():
    pattern = ParametricPattern(
        [
            LineSegment("left", (0, 50), (0, 0)),
            LineSegment("bottom", (0, 0), (100, 0)),
            LineSegment("right", (100, 0), (100, 50)),
            LineSegment("top", (100, 50), (0, 50)),
        ]
    )
    mesh = triangulate(pattern)
    assert mesh.boundary_edge_segment_ids == ("left", "bottom", "right", "top")


def test_clockwise_outline_keeps_segment_provenance_on_normalization():
    # This order is genuinely clockwise: bottom-left -> top-left -> top-right -> bottom-right.
    pattern = ParametricPattern(
        [
            LineSegment("left", (0, 0), (0, 50)),
            LineSegment("top", (0, 50), (100, 50)),
            LineSegment("right", (100, 50), (100, 0)),
            LineSegment("bottom", (100, 0), (0, 0)),
        ]
    )
    mesh = triangulate(pattern)
    assert mesh.boundary_edge_segment_ids == ("right", "top", "left", "bottom")


def test_linear_boundary_refinement_preserves_authored_segment_identity_and_spacing():
    pattern = ParametricPattern(
        [
            LineSegment("side", (0, 0), (100, 0)),
            LineSegment("back", (100, 0), (100, 50)),
            LineSegment("top", (100, 50), (0, 50)),
            LineSegment("left", (0, 50), (0, 0)),
        ]
    )
    refined = refine_linear_boundary(pattern, 20.0)
    mesh = triangulate(refined)
    assert len(mesh.boundary_vertex_indices) > 4
    ids = mesh.boundary_edge_segment_ids
    assert all(
        identifier == authored or identifier.startswith(authored + "::sub::")
        for authored in ("side", "back", "top", "left")
        for identifier in ids
        if identifier.startswith(authored)
    )
    assert any(identifier.startswith("side::sub::") for identifier in ids)
    points = mesh.vertices
    assert (
        max(
            ((points[a][0] - points[b][0]) ** 2 + (points[a][1] - points[b][1]) ** 2) ** 0.5
            for a, b in mesh.boundary_edges()
        )
        <= 20.000001
    )


def test_seam_generates_stitches():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    constraints = build_sewing_constraints(
        a, ma, b, mb, Seam("front", 1, "back", 3, id="side"), samples=5
    )
    assert len(constraints.stitches) >= 2
    constraints.validate()


def test_triangulation_rejects_nonfinite_area_limits() -> None:
    """NaN and infinity must not bypass the maximum-area positivity guard."""
    for max_area in (float("nan"), float("inf")):
        try:
            triangulate(rectangle(10.0, 10.0), max_area=max_area)
        except ValueError as exc:
            assert "finite" in str(exc).lower()
        else:
            raise AssertionError("non-finite max_area was accepted")


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("mesh tests passed")



def test_sewing_constraints_respect_explicit_b_reversal():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    seam = Seam("front", "right", "back", "left", id="side", reversed_b=True)
    constraints = build_sewing_constraints(a, ma, b, mb, seam, samples=2)
    pairs = [(ma.vertices[s.vertex_a], mb.vertices[s.vertex_b]) for s in constraints.stitches]
    # Rectangle right edge runs bottom-to-top; left edge runs top-to-bottom.
    assert pairs[0][0][1] == 0.0
    assert pairs[0][1][1] == 0.0
    assert pairs[-1][0][1] == 50.0
    assert pairs[-1][1][1] == 50.0


def test_sewing_constraints_use_explicit_b_orientation_when_not_reversed():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    seam = Seam("front", "right", "back", "left", id="side", reversed_b=False)
    constraints = build_sewing_constraints(a, ma, b, mb, seam, samples=2)
    pairs = [(ma.vertices[s.vertex_a], mb.vertices[s.vertex_b]) for s in constraints.stitches]
    assert pairs[0][0][1] == 0.0
    assert pairs[0][1][1] == 50.0
    assert pairs[-1][0][1] == 50.0
    assert pairs[-1][1][1] == 0.0


def test_sewing_constraints_apply_partial_seam_ranges():
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary

    a = refine_linear_boundary(rectangle(100.0, 100.0), 10.0)
    b = refine_linear_boundary(rectangle(100.0, 100.0), 10.0)
    ma, mb = triangulate(a), triangulate(b)
    seam = Seam(
        "front", "right", "back", "left", id="partial",
        start_a=0.2, end_a=0.8, start_b=0.1, end_b=0.7, reversed_b=True,
    )
    constraints = build_sewing_constraints(a, ma, b, mb, seam, samples=2)
    pairs = [(ma.vertices[s.vertex_a], mb.vertices[s.vertex_b]) for s in constraints.stitches]
    assert pairs[0][0][1] == 20.0
    assert pairs[0][1][1] == pytest.approx(30.0)
    assert pairs[-1][0][1] == 80.0
    assert pairs[-1][1][1] == 90.0



def test_sewing_constraints_allow_equal_local_indices_across_panel_meshes():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    constraints = build_sewing_constraints(
        a, ma, b, mb, Seam("front", "bottom", "back", "bottom", id="hem"), samples=2
    )
    assert constraints.seam_map["front:bottom-back:bottom"] == ((0, 0), (1, 1))
    constraints.validate()


def test_sewing_constraints_never_select_a_nearby_unrelated_boundary():
    polygon = ParametricPattern(
        [
            LineSegment("bottom", (0.0, 0.0), (100.0, 0.0)),
            LineSegment("right", (100.0, 0.0), (100.0, 100.0)),
            LineSegment("top", (100.0, 100.0), (0.0, 100.0)),
            LineSegment("upper-left", (0.0, 100.0), (0.0, 60.0)),
            LineSegment("notch-upper", (0.0, 60.0), (99.0, 51.0)),
            LineSegment("notch", (99.0, 51.0), (99.0, 49.0)),
            LineSegment("notch-lower", (99.0, 49.0), (0.0, 40.0)),
            LineSegment("lower-left", (0.0, 40.0), (0.0, 0.0)),
        ]
    )
    regular = rectangle(100.0, 100.0)
    mesh_a, mesh_b = triangulate(polygon), triangulate(regular)
    constraints = build_sewing_constraints(
        polygon, mesh_a, regular, mesh_b,
        Seam("front", "right", "back", "left", id="right-to-left", reversed_b=True),
        samples=3,
    )
    middle = constraints.stitches[1]
    x, y = mesh_a.vertices[middle.vertex_a]
    assert x == 100.0
    assert y in (0.0, 100.0)

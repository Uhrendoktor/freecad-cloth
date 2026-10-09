from math import cos, sin, tau

from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    rectangle,
    seam_allowance_outline,
)
from freecad_cloth.pattern.PatternMesh import _self_intersects, _self_intersects_python


def test_rectangle_allowance_offsets_every_side():
    outline = seam_allowance_outline(rectangle(100.0, 60.0), 5.0)
    assert outline == [(-5.0, -5.0), (105.0, -5.0), (105.0, 65.0), (-5.0, 65.0)]


def test_zero_allowance_preserves_source_outline():
    pattern = rectangle(100.0, 60.0)
    assert seam_allowance_outline(pattern, 0.0) == pattern.sampled_outline()


def test_reversed_boundary_offsets_outward_too():
    pattern = ParametricPattern(
        [
            LineSegment("left", (0.0, 0.0), (0.0, 60.0)),
            LineSegment("top", (0.0, 60.0), (100.0, 60.0)),
            LineSegment("right", (100.0, 60.0), (100.0, 0.0)),
            LineSegment("bottom", (100.0, 0.0), (0.0, 0.0)),
        ]
    )
    assert seam_allowance_outline(pattern, 5.0) == [
        (-5.0, -5.0),
        (-5.0, 65.0),
        (105.0, 65.0),
        (105.0, -5.0),
    ]


def test_concave_boundary_is_deterministic():
    pattern = ParametricPattern(
        [
            LineSegment("a", (0.0, 0.0), (40.0, 0.0)),
            LineSegment("b", (40.0, 0.0), (40.0, 20.0)),
            LineSegment("c", (40.0, 20.0), (20.0, 20.0)),
            LineSegment("d", (20.0, 20.0), (20.0, 40.0)),
            LineSegment("e", (20.0, 40.0), (0.0, 40.0)),
            LineSegment("f", (0.0, 40.0), (0.0, 0.0)),
        ]
    )
    first = seam_allowance_outline(pattern, 2.0)
    assert first == seam_allowance_outline(pattern, 2.0)
    assert len(first) == 6


def test_invalid_allowance_is_rejected():
    try:
        seam_allowance_outline(rectangle(100.0, 60.0), -1.0)
    except ValueError:
        return
    raise AssertionError("negative seam allowance must be rejected")


def test_large_simple_ring_matches_intersection_reference():
    """The optional GEOS fast path agrees with the Python oracle on a simple ring."""
    points = tuple((cos(tau * index / 64), sin(tau * index / 64)) for index in range(64))
    assert not _self_intersects_python(points)
    assert not _self_intersects(points)


def test_suspicious_crossing_outline_uses_tolerance_aware_reference():
    """Potential intersections retain the existing Python predicate as authority."""
    bow_tie = ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0))
    points = tuple(bow_tie[index % len(bow_tie)] for index in range(64))
    assert _self_intersects_python(points)
    assert _self_intersects(points)


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("pattern geometry tests passed")

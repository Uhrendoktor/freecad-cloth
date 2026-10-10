from collections.abc import Sequence
from math import cos, pi, sin, tau

import pytest
from shapely.geometry import Polygon

from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    Point,
    rectangle,
    seam_allowance_outline,
    signed_area,
)
from freecad_cloth.pattern.PatternMesh import _self_intersects


def _python_self_intersects_reference(points: Sequence[Point]) -> bool:
    """Test-only copy of the former segment predicate for regression comparisons."""

    def cross(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        for j in range(i + 1, len(points)):
            if j in (i, (i + 1) % len(points), (i - 1) % len(points)):
                continue
            c, d = points[j], points[(j + 1) % len(points)]
            values = (cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b))
            if values[0] * values[1] < -1e-10 and values[2] * values[3] < -1e-10:
                return True
    return False


def test_signed_area_preserves_orientation():
    ccw = ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0))
    assert signed_area(ccw) == 2.0
    assert signed_area(tuple(reversed(ccw))) == -2.0
    assert signed_area(()) == 0.0


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
    with pytest.raises(ValueError):
        seam_allowance_outline(rectangle(100.0, 60.0), -1.0)


def test_large_simple_ring_matches_intersection_reference():
    """Required GEOS predicate agrees with the former Python oracle on a simple ring."""
    points = tuple((cos(tau * index / 64), sin(tau * index / 64)) for index in range(64))
    assert not _python_self_intersects_reference(points)
    assert not _self_intersects(points)


def test_geos_detects_a_crossing_outline():
    """GEOS and the test-only reference both detect a crossing polygon outline."""
    points = ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0))
    assert _python_self_intersects_reference(points)
    assert _self_intersects(points)


def _pattern_from_outline(points: Sequence[Point]) -> ParametricPattern:
    """Build a closed piecewise-linear pattern from ordered points."""
    return ParametricPattern(
        [
            LineSegment(f"edge-{index}", point, points[(index + 1) % len(points)])
            for index, point in enumerate(points)
        ]
    )


def test_allowance_closes_narrow_concave_notch_without_self_intersection():
    points = (
        (0.0, 0.0),
        (20.0, 0.0),
        (20.0, 20.0),
        (12.0, 20.0),
        (12.0, 4.0),
        (8.0, 4.0),
        (8.0, 20.0),
        (0.0, 20.0),
    )
    outline = seam_allowance_outline(_pattern_from_outline(points), 3.0)
    offset = Polygon(outline)

    assert offset.is_valid
    assert offset.exterior.is_simple
    assert len(outline) < len(points)
    assert offset.area > Polygon(points).area


def test_allowance_rejects_self_intersecting_source_outline():
    points = tuple(
        (cos(2.0 * pi * ((2 * index) % 5) / 5), sin(2.0 * pi * ((2 * index) % 5) / 5))
        for index in range(5)
    )
    with pytest.raises(ValueError, match="valid simple polygon"):
        seam_allowance_outline(_pattern_from_outline(points), 0.5)


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("pattern geometry tests passed")

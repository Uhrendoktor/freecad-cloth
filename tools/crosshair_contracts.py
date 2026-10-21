# Copyright (C) 2026 FreeCAD Cloth contributors
"""Symbolic contracts that call production Python math implementations.

CrossHair explores these contracts with symbolic inputs and reports counterexamples.
The contracts intentionally target pure, bounded helpers rather than FreeCAD/OCCT
objects or native solver state, which CrossHair cannot model exhaustively.
"""

from __future__ import annotations

from typing import NamedTuple, cast

from freecad_cloth.pattern.PatternGeometry import (
    _distance,
    _lerp,
    _line_intersection,
    signed_area,
)
from freecad_cloth.sewing.SewingCorrespondence import map_parameter
from freecad_cloth.simulation.ClothSolver import Particle, distance


class _CoordinatePoint(NamedTuple):
    """Structural point used to avoid symbolic execution inside Pydantic validation."""

    x: float
    y: float
    z: float


def particle_distance_contract(
    ax: float, ay: float, az: float, bx: float, by: float, bz: float
) -> float:
    """Check solver distance identities using structurally compatible symbolic points.

    Args:
        ax: First particle's x coordinate.
        ay: First particle's y coordinate.
        az: First particle's z coordinate.
        bx: Second particle's x coordinate.
        by: Second particle's y coordinate.
        bz: Second particle's z coordinate.

    Returns:
        Non-negative Euclidean distance between the two particles.

    pre: -1e6 <= ax <= 1e6
    pre: -1e6 <= ay <= 1e6
    pre: -1e6 <= az <= 1e6
    pre: -1e6 <= bx <= 1e6
    pre: -1e6 <= by <= 1e6
    pre: -1e6 <= bz <= 1e6
    """
    a = cast("Particle", _CoordinatePoint(ax, ay, az))
    b = cast("Particle", _CoordinatePoint(bx, by, bz))
    result = distance(a, b)
    assert result >= 0.0
    assert distance(a, a) == 0.0
    assert distance(a, b) == distance(b, a)
    return result


def normalized_seam_mapping_contract(parameter_a: float, reversed_b: bool) -> float:
    """Check direction complement and normalized bounds on the real seam mapper.

    Args:
        parameter_a: Normalized parameter on the source seam.
        reversed_b: Whether the destination seam orientation is reversed.

    Returns:
        Normalized destination parameter after orientation mapping.

    pre: 0.0 <= parameter_a <= 1.0
    """
    result = map_parameter(parameter_a, reversed_b=reversed_b)
    complementary = map_parameter(parameter_a, reversed_b=not reversed_b)
    assert 0.0 <= result <= 1.0
    assert 0.0 <= complementary <= 1.0
    assert result + complementary == 1.0
    return result


def ranged_seam_mapping_contract(
    parameter_a: float,
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
    reversed_b: bool,
) -> float:
    """Check range mapping for normalized intervals.

    Args:
        parameter_a: Normalized parameter on the source seam.
        start_a: Lower source parameter bound for the mapped interval.
        end_a: Upper source parameter bound for the mapped interval.
        start_b: Lower destination parameter bound for the mapped interval.
        end_b: Upper destination parameter bound for the mapped interval.
        reversed_b: Whether the destination interval is traversed in reverse.

    Returns:
        Parameter mapped into the destination seam interval.

    pre: 0.0 <= parameter_a <= 1.0
    pre: 0.0 <= start_a < end_a <= 1.0
    pre: 0.0 <= start_b < end_b <= 1.0
    """
    result = map_parameter(parameter_a, start_a, end_a, start_b, end_b, reversed_b)
    assert start_b <= result <= end_b
    if parameter_a == start_a:
        assert result == (end_b if reversed_b else start_b)
    if parameter_a == end_a:
        assert result == (start_b if reversed_b else end_b)
    return result


def interpolation_contract(start: float, end: float, fraction: float) -> float:
    """Check the production interpolation helper preserves its convex interval.

    Args:
        start: Initial value of the interpolation interval.
        end: Final value of the interpolation interval.
        fraction: Relative position between the interval endpoints.

    Returns:
        Interpolated value bounded by the two endpoints.

    pre: -1e100 <= start <= 1e100
    pre: -1e100 <= end <= 1e100
    pre: 0.0 <= fraction <= 1.0
    """
    result = _lerp(start, end, fraction)
    assert min(start, end) <= result <= max(start, end)
    if fraction == 0.0:
        assert result == start
    if fraction == 1.0:
        assert result == end
    return result


def parallel_line_intersection_contract(y: float) -> None:
    """Parallel, distinct lines must not produce a finite intersection.

    Args:
        y: Vertical coordinate of the first horizontal line.

    pre: -1e6 <= y <= 1e6
    """
    result = _line_intersection((0.0, y), (1.0, y), (0.0, y + 1.0), (1.0, y + 1.0))
    assert result is None


def perpendicular_line_intersection_contract(x: float, y: float) -> tuple[float, float]:
    """Check the production line-intersection math on symbolic perpendicular lines.

    Args:
        x: Horizontal coordinate of the vertical line.
        y: Vertical coordinate of the horizontal line.

    Returns:
        Intersection coordinates of the perpendicular lines.

    pre: -1e6 <= x <= 1e6
    pre: -1e6 <= y <= 1e6
    """
    result = _line_intersection((-1.0, y), (1.0, y), (x, -1.0), (x, 1.0))
    assert result is not None
    assert abs(result[0] - x) <= 1e-9
    assert abs(result[1] - y) <= 1e-9
    return result


def polygon_area_orientation_contract(side: float) -> float:
    """Check polygon signed area scales quadratically and flips under orientation reversal.

    Args:
        side: Non-negative side length of the square.

    Returns:
        Signed area of the square in its original orientation.

    pre: 0.0 <= side <= 1e6
    """
    square = ((0.0, 0.0), (side, 0.0), (side, side), (0.0, side))
    reversed_square = tuple(reversed(square))
    area = signed_area(square)
    reversed_area = signed_area(reversed_square)
    assert area == side * side
    assert reversed_area == -area
    return area


def point_distance_contract(x: float, y: float) -> float:
    """Check the production Euclidean distance is non-negative and symmetric.

    Args:
        x: Horizontal displacement from the origin.
        y: Vertical displacement from the origin.

    Returns:
        Euclidean distance from the origin to the supplied point.

    pre: -1e100 <= x <= 1e100
    pre: -1e100 <= y <= 1e100
    """
    result = _distance((0.0, 0.0), (x, y))
    assert result >= 0.0
    assert result == _distance((x, y), (0.0, 0.0))
    if x == 0.0 and y == 0.0:
        assert result == 0.0
    return result

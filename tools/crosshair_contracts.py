# Copyright (C) 2026 FreeCAD Cloth contributors
"""Symbolic contracts that call production Python math implementations.

CrossHair explores these contracts with symbolic inputs and reports counterexamples.
The contracts intentionally target pure, bounded helpers rather than FreeCAD/OCCT
objects or native solver state, which CrossHair cannot model exhaustively.
"""

from __future__ import annotations

from importlib import import_module
from math import isclose
from typing import Callable, NamedTuple, cast

from freecad_cloth.sewing.SewingCorrespondence import map_parameter
from freecad_cloth.simulation.ClothSolver import Particle, distance

COORDINATE_LIMIT = 1e6
LARGE_FLOAT_LIMIT = 1e100
ABSOLUTE_TEST_TOLERANCE = 1e-9

_PATTERN_GEOMETRY = import_module("freecad_cloth.pattern.PatternGeometry")
_PRODUCTION_LERP = cast("Callable[[float, float, float], float]", vars(_PATTERN_GEOMETRY)["_lerp"])
_PRODUCTION_LINE_INTERSECTION = cast(
    "Callable[[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]], tuple[float, float] | None]",
    vars(_PATTERN_GEOMETRY)["_line_intersection"],
)
_PRODUCTION_DISTANCE_2D = cast(
    "Callable[[tuple[float, float], tuple[float, float]], float]",
    vars(_PATTERN_GEOMETRY)["_distance"],
)
_PRODUCTION_SIGNED_AREA = cast(
    "Callable[[tuple[tuple[float, float], ...]], float]",
    vars(_PATTERN_GEOMETRY)["signed_area"],
)


class _CoordinatePoint(NamedTuple):
    """Structural point used to avoid symbolic execution inside Pydantic validation."""

    x: float
    y: float
    z: float


def _require(*, condition: bool, message: str) -> None:
    """Raise when a symbolic contract condition is false.

    Args:
        condition: Invariant that must hold for the contract to be satisfied.
        message: Diagnostic describing the violated invariant.

    Raises:
        AssertionError: If the invariant does not hold.
    """
    if not condition:
        raise AssertionError(message)


def particle_distance_contract(
    point_a: tuple[float, float, float],
    point_b: tuple[float, float, float],
) -> float:
    """Check solver distance identities using structurally compatible symbolic points.

    Args:
        point_a: X, Y, and Z coordinates of the first particle.
        point_b: X, Y, and Z coordinates of the second particle.

    Returns:
        Non-negative Euclidean distance between the two particles.

    pre: -COORDINATE_LIMIT <= point_a[0] <= COORDINATE_LIMIT
    pre: -COORDINATE_LIMIT <= point_a[1] <= COORDINATE_LIMIT
    pre: -COORDINATE_LIMIT <= point_a[2] <= COORDINATE_LIMIT
    pre: -COORDINATE_LIMIT <= point_b[0] <= COORDINATE_LIMIT
    pre: -COORDINATE_LIMIT <= point_b[1] <= COORDINATE_LIMIT
    pre: -COORDINATE_LIMIT <= point_b[2] <= COORDINATE_LIMIT
    """
    a = cast("Particle", _CoordinatePoint(*point_a))
    b = cast("Particle", _CoordinatePoint(*point_b))
    result = distance(a, b)
    _require(condition=result >= 0.0, message="particle distance must be non-negative")
    self_distance = distance(a, a)
    _require(
        condition=isclose(self_distance, 0.0, rel_tol=0.0, abs_tol=0.0),
        message="distance from a particle to itself must be zero",
    )
    reverse_distance = distance(b, a)
    _require(
        condition=isclose(result, reverse_distance, rel_tol=0.0, abs_tol=0.0),
        message="particle distance must be symmetric",
    )
    return result


def normalized_seam_mapping_contract(parameter_a: float, *, reversed_b: bool) -> float:
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
    _require(condition=0.0 <= result <= 1.0, message="mapped parameter must be normalized")
    _require(
        condition=0.0 <= complementary <= 1.0,
        message="complementary mapped parameter must be normalized",
    )
    _require(
        condition=isclose(
            result + complementary,
            1.0,
            rel_tol=0.0,
            abs_tol=ABSOLUTE_TEST_TOLERANCE,
        ),
        message="opposite seam orientations must map to complementary parameters",
    )
    return result


def ranged_seam_mapping_contract(
    parameter_a: float,
    source_range: tuple[float, float],
    target_range: tuple[float, float],
    *,
    reversed_b: bool,
) -> float:
    """Check range mapping for normalized source and destination intervals.

    Args:
        parameter_a: Normalized parameter on the source seam.
        source_range: Start and end parameter bounds on the source seam.
        target_range: Start and end parameter bounds on the destination seam.
        reversed_b: Whether the destination interval is traversed in reverse.

    Returns:
        Parameter mapped into the destination seam interval.

    pre: 0.0 <= parameter_a <= 1.0
    pre: 0.0 <= source_range[0] < source_range[1] <= 1.0
    pre: 0.0 <= target_range[0] < target_range[1] <= 1.0
    """
    result = map_parameter(
        parameter_a,
        *source_range,
        *target_range,
        reversed_b=reversed_b,
    )
    target_start, target_end = target_range
    _require(
        condition=target_start <= result <= target_end,
        message="mapped parameter must stay within the destination interval",
    )
    if isclose(parameter_a, source_range[0], rel_tol=0.0, abs_tol=0.0):
        expected = target_end if reversed_b else target_start
        _require(
            condition=isclose(result, expected, rel_tol=0.0, abs_tol=0.0),
            message="source interval start must map to the matching destination endpoint",
        )
    if isclose(parameter_a, source_range[1], rel_tol=0.0, abs_tol=0.0):
        expected = target_start if reversed_b else target_end
        _require(
            condition=isclose(result, expected, rel_tol=0.0, abs_tol=0.0),
            message="source interval end must map to the matching destination endpoint",
        )
    return result


def interpolation_contract(start: float, end: float, fraction: float) -> float:
    """Check the production interpolation helper preserves its convex interval.

    Args:
        start: Initial value of the interpolation interval.
        end: Final value of the interpolation interval.
        fraction: Relative position between the interval endpoints.

    Returns:
        Interpolated value bounded by the two endpoints.

    pre: -LARGE_FLOAT_LIMIT <= start <= LARGE_FLOAT_LIMIT
    pre: -LARGE_FLOAT_LIMIT <= end <= LARGE_FLOAT_LIMIT
    pre: 0.0 <= fraction <= 1.0
    """
    result = _PRODUCTION_LERP(start, end, fraction)
    _require(
        condition=min(start, end) <= result <= max(start, end),
        message="interpolated value must remain inside its endpoint interval",
    )
    if isclose(fraction, 0.0, rel_tol=0.0, abs_tol=0.0):
        _require(
            condition=isclose(result, start, rel_tol=0.0, abs_tol=0.0),
            message="zero interpolation fraction must return the start value",
        )
    if isclose(fraction, 1.0, rel_tol=0.0, abs_tol=0.0):
        _require(
            condition=isclose(result, end, rel_tol=0.0, abs_tol=0.0),
            message="unit interpolation fraction must return the end value",
        )
    return result


def parallel_line_intersection_contract(y: float) -> None:
    """Parallel, distinct lines must not produce a finite intersection.

    Args:
        y: Vertical coordinate of the first horizontal line.

    pre: -COORDINATE_LIMIT <= y <= COORDINATE_LIMIT
    """
    result = _PRODUCTION_LINE_INTERSECTION(
        (0.0, y),
        (1.0, y),
        (0.0, y + 1.0),
        (1.0, y + 1.0),
    )
    _require(condition=result is None, message="distinct parallel lines must not intersect")


def perpendicular_line_intersection_contract(x: float, y: float) -> tuple[float, float]:
    """Check the production line-intersection math on symbolic perpendicular lines.

    Args:
        x: Horizontal coordinate of the vertical line.
        y: Vertical coordinate of the horizontal line.

    Returns:
        Intersection coordinates of the perpendicular lines.

    pre: -COORDINATE_LIMIT <= x <= COORDINATE_LIMIT
    pre: -COORDINATE_LIMIT <= y <= COORDINATE_LIMIT
    """
    result = _PRODUCTION_LINE_INTERSECTION(
        (-1.0, y),
        (1.0, y),
        (x, -1.0),
        (x, 1.0),
    )
    _require(condition=result is not None, message="perpendicular lines must intersect")
    point = cast("tuple[float, float]", result)
    _require(
        condition=isclose(
            point[0],
            x,
            rel_tol=0.0,
            abs_tol=ABSOLUTE_TEST_TOLERANCE,
        ),
        message="intersection horizontal coordinate must match the vertical line",
    )
    _require(
        condition=isclose(
            point[1],
            y,
            rel_tol=0.0,
            abs_tol=ABSOLUTE_TEST_TOLERANCE,
        ),
        message="intersection vertical coordinate must match the horizontal line",
    )
    return point


def polygon_area_orientation_contract(side: float) -> float:
    """Check polygon signed area scales quadratically and flips under orientation reversal.

    Args:
        side: Non-negative side length of the square.

    Returns:
        Signed area of the square in its original orientation.

    pre: 0.0 <= side <= COORDINATE_LIMIT
    """
    square = ((0.0, 0.0), (side, 0.0), (side, side), (0.0, side))
    reversed_square = tuple(reversed(square))
    area = _PRODUCTION_SIGNED_AREA(square)
    reversed_area = _PRODUCTION_SIGNED_AREA(reversed_square)
    expected_area = side * side
    _require(
        condition=isclose(
            area,
            expected_area,
            rel_tol=ABSOLUTE_TEST_TOLERANCE,
            abs_tol=ABSOLUTE_TEST_TOLERANCE,
        ),
        message="square signed area must equal its side length squared",
    )
    _require(
        condition=isclose(
            reversed_area,
            -area,
            rel_tol=ABSOLUTE_TEST_TOLERANCE,
            abs_tol=ABSOLUTE_TEST_TOLERANCE,
        ),
        message="reversing polygon orientation must negate signed area",
    )
    return area


def point_distance_contract(x: float, y: float) -> float:
    """Check the production Euclidean distance is non-negative and symmetric.

    Args:
        x: Horizontal displacement from the origin.
        y: Vertical displacement from the origin.

    Returns:
        Euclidean distance from the origin to the supplied point.

    pre: -LARGE_FLOAT_LIMIT <= x <= LARGE_FLOAT_LIMIT
    pre: -LARGE_FLOAT_LIMIT <= y <= LARGE_FLOAT_LIMIT
    """
    origin = (0.0, 0.0)
    point = (x, y)
    result = _PRODUCTION_DISTANCE_2D(origin, point)
    _require(condition=result >= 0.0, message="Euclidean distance must be non-negative")
    reverse_result = _PRODUCTION_DISTANCE_2D(point, origin)
    _require(
        condition=isclose(result, reverse_result, rel_tol=0.0, abs_tol=0.0),
        message="Euclidean distance must be symmetric",
    )
    if isclose(x, 0.0, rel_tol=0.0, abs_tol=0.0) and isclose(
        y,
        0.0,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        _require(
            condition=isclose(result, 0.0, rel_tol=0.0, abs_tol=0.0),
            message="distance from the origin to itself must be zero",
        )
    return result

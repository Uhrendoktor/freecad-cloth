# Copyright (C) 2026 FreeCAD Cloth contributors
"""Share native circular-arc construction across FreeCAD acceptance fixtures."""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from types import ModuleType

_DETERMINANT_TOLERANCE = 1e-9
_MINIMUM_RADIUS_MM = 1e-9
_MINIMUM_SWEEP_RADIANS = 1e-9
_ARC_FIDELITY_TOLERANCE_MM = 1e-5
_FULL_TURN_RADIANS = 2.0 * math.pi


class _Point2D(Protocol):
    """Describe planar coordinates exposed by native FreeCAD geometry."""

    x: float
    y: float


_AxisPair = tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True, slots=True)
class _CircleGeometry:
    """Store the center and radius calculated from three authored points.

    Attributes:
        center_x: Horizontal coordinate of the circle center in millimeters.
        center_y: Vertical coordinate of the circle center in millimeters.
        radius: Positive circle radius in millimeters.
    """

    center_x: float
    center_y: float
    radius: float


@dataclass(frozen=True, slots=True)
class _CircleSweep:
    """Store a native circle's minor angular sweep through the authored midpoint.

    Attributes:
        circle: Native FreeCAD circle whose parameter basis was inspected.
        normal_z: Z component of the normal that contains the selected sweep.
        start_angle: Native start parameter for the selected sweep.
        sweep: Positive angular length of the selected minor sweep.
        middle_sweep: Midpoint's angular offset from the selected start.
    """

    circle: object
    normal_z: float
    start_angle: float
    sweep: float
    middle_sweep: float


def _circle_geometry(
    start: _Point2D, end: _Point2D, midpoint: _Point2D
) -> _CircleGeometry:
    """Calculate the unique circle passing through three planar points.

    Args:
        start: Authored two-dimensional start point in millimeters.
        end: Authored two-dimensional end point in millimeters.
        midpoint: Authored on-arc point in millimeters.

    Returns:
        Center coordinates and positive radius for the calculated circle.

    Raises:
        RuntimeError: If the points are collinear or the circle radius is invalid.
    """
    start_x, start_y = float(start.x), float(start.y)
    end_x, end_y = float(end.x), float(end.y)
    middle_x, middle_y = float(midpoint.x), float(midpoint.y)
    start_squared = start_x * start_x + start_y * start_y
    end_squared = end_x * end_x + end_y * end_y
    middle_squared = middle_x * middle_x + middle_y * middle_y
    determinant = 2.0 * (
        start_x * (end_y - middle_y) + end_x * (middle_y - start_y) + middle_x * (start_y - end_y)
    )
    if abs(determinant) <= _DETERMINANT_TOLERANCE:
        msg = "tunic armhole points are collinear; cannot construct an arc"
        raise RuntimeError(msg)

    center_x = (
        start_squared * (end_y - middle_y)
        + end_squared * (middle_y - start_y)
        + middle_squared * (start_y - end_y)
    ) / determinant
    center_y = (
        start_squared * (middle_x - end_x)
        + end_squared * (start_x - middle_x)
        + middle_squared * (end_x - start_x)
    ) / determinant
    radius = math.hypot(start_x - center_x, start_y - center_y)
    if not math.isfinite(radius) or radius <= _MINIMUM_RADIUS_MM:
        msg = "tunic armhole circle has an invalid radius"
        raise RuntimeError(msg)
    return _CircleGeometry(center_x, center_y, radius)


def _native_curve_value(curve: object, parameter_value: float) -> _Point2D:
    """Evaluate a native circle or arc at one parameter.

    Args:
        curve: Native FreeCAD circle or arc to evaluate.
        parameter_value: Native curve parameter to evaluate.

    Returns:
        Evaluated point exposing x and y coordinates.

    Raises:
        TypeError: If the native curve provides no supported parameter evaluator.
    """
    getter = getattr(curve, "valueAt", None)
    if not callable(getter):
        getter = getattr(curve, "value", None)
    if not callable(getter):
        msg = "tunic armhole curve has no native parameter evaluator"
        raise TypeError(msg)
    return cast("_Point2D", getter(float(parameter_value)))


def _circle_axes(circle: object, geometry: _CircleGeometry) -> _AxisPair:
    """Read unit axes from the native circle's own parameter basis.

    Args:
        circle: Native FreeCAD circle whose basis should be inspected.
        geometry: Center and radius used to normalize its basis vectors.

    Returns:
        The native circle's planar x and y unit axes.
    """
    zero_point = _native_curve_value(circle, 0.0)
    quarter_point = _native_curve_value(circle, math.pi / 2.0)
    axis_x = (
        (float(zero_point.x) - geometry.center_x) / geometry.radius,
        (float(zero_point.y) - geometry.center_y) / geometry.radius,
    )
    axis_y = (
        (float(quarter_point.x) - geometry.center_x) / geometry.radius,
        (float(quarter_point.y) - geometry.center_y) / geometry.radius,
    )
    return axis_x, axis_y


def _parameter_for_point(
    point: _Point2D,
    geometry: _CircleGeometry,
    axes: _AxisPair,
) -> float:
    """Convert a planar point to an angle in the native circle basis.

    Args:
        point: Authored point whose circle parameter should be calculated.
        geometry: Circle center and radius used to express point displacement.
        axes: Unit x and y axes read from the native circle.

    Returns:
        Angle normalized from zero up to one full turn.
    """
    axis_x, axis_y = axes
    delta_x = float(point.x) - geometry.center_x
    delta_y = float(point.y) - geometry.center_y
    return (
        math.atan2(
            delta_x * axis_y[0] + delta_y * axis_y[1],
            delta_x * axis_x[0] + delta_y * axis_x[1],
        )
        % _FULL_TURN_RADIANS
    )


def _select_circle_sweep(
    part_api: ModuleType,
    app_api: ModuleType,
    geometry: _CircleGeometry,
    points: tuple[_Point2D, _Point2D, _Point2D],
) -> _CircleSweep | None:
    """Find a circle orientation whose positive sweep contains all three points.

    Args:
        part_api: FreeCAD Part module used to construct native circles.
        app_api: FreeCAD application module used to construct vectors.
        geometry: Computed center and radius shared by candidate circles.
        points: Authored start, end, and on-arc midpoint in source order.

    Returns:
        The candidate sweep that contains the midpoint, or None if neither normal works.
    """
    start, end, midpoint = points
    for normal_z in (1.0, -1.0):
        circle = part_api.Circle(
            app_api.Vector(geometry.center_x, geometry.center_y, 0.0),
            app_api.Vector(0.0, 0.0, normal_z),
            geometry.radius,
        )
        axes = _circle_axes(circle, geometry)
        start_angle = _parameter_for_point(start, geometry, axes)
        end_angle = _parameter_for_point(end, geometry, axes)
        middle_angle = _parameter_for_point(midpoint, geometry, axes)
        sweep = (end_angle - start_angle) % _FULL_TURN_RADIANS
        middle_sweep = (middle_angle - start_angle) % _FULL_TURN_RADIANS
        if sweep > _MINIMUM_SWEEP_RADIANS and middle_sweep <= sweep + _MINIMUM_SWEEP_RADIANS:
            return _CircleSweep(circle, normal_z, start_angle, sweep, middle_sweep)
    return None


def arc_through_midpoint(
    part_module: ModuleType,
    start: _Point2D,
    end: _Point2D,
    midpoint: _Point2D,
) -> object:
    """Construct the minor native circular arc through three authored points.

    Args:
        part_module: Native FreeCAD Part module providing circle and arc constructors.
        start: Authored two-dimensional start point of the arc in millimeters.
        end: Authored two-dimensional end point of the arc in millimeters.
        midpoint: Authored point selecting the intended minor sweep in millimeters.

    Returns:
        Native FreeCAD ArcOfCircle preserving the three authored points.

    Raises:
        RuntimeError: If points are collinear, a consistent minor arc cannot be built,
            or the native arc loses geometric fidelity.
        TypeError: If a native FreeCAD curve lacks a supported parameter evaluator.
    """
    part_api = cast("ModuleType", part_module)
    app_api = importlib.import_module("FreeCAD")
    geometry = _circle_geometry(start, end, midpoint)
    selected = _select_circle_sweep(part_api, app_api, geometry, (start, end, midpoint))
    if selected is None:
        msg = "tunic armhole points do not define a consistent circular sweep"
        raise RuntimeError(msg)
    if selected.sweep >= math.pi:
        raise RuntimeError(
            f"tunic armhole through-point selects a major arc: sweep-rad={selected.sweep:.6f}"
        )

    arc = part_api.ArcOfCircle(
        selected.circle,
        selected.start_angle,
        selected.start_angle + selected.sweep,
    )
    checks = (
        ("start", start, selected.start_angle),
        ("end", end, selected.start_angle + selected.sweep),
        ("midpoint", midpoint, selected.start_angle + selected.middle_sweep),
    )
    for role, expected, parameter_value in checks:
        actual = _native_curve_value(arc, parameter_value)
        error = math.hypot(
            float(actual.x) - float(expected.x),
            float(actual.y) - float(expected.y),
        )
        if error > _ARC_FIDELITY_TOLERANCE_MM:
            msg = (
                f"tunic armhole arc lost authored {role}: error-mm={error:.6f} "
                f"normal-z={selected.normal_z:.0f} "
                f"expected=({float(expected.x):.4f},{float(expected.y):.4f}) "
                f"actual=({float(actual.x):.4f},{float(actual.y):.4f})"
            )
            raise RuntimeError(msg)
    return arc

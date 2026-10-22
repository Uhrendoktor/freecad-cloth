# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared native circular-arc construction for FreeCAD acceptance fixtures."""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable
from typing import Protocol, cast


class _Point2D(Protocol):
    """Describe the planar coordinate properties exposed by native geometry."""

    x: float
    y: float


def arc_through_midpoint(
    part_module: object,
    start: _Point2D,
    end: _Point2D,
    midpoint: _Point2D,
) -> object:
    """Construct the minor native circle arc passing through three authored points.

    Args:
        part_module: Native FreeCAD Part module providing circle and arc constructors.
        start: Authored two-dimensional start point of the arc.
        end: Authored two-dimensional end point of the arc.
        midpoint: Authored point that selects the intended minor sweep.

    Returns:
        A native FreeCAD ArcOfCircle preserving the three authored points.

    Raises:
        RuntimeError: If the points are collinear, inconsistent, or lose geometric fidelity.
    """
    app_module = importlib.import_module("FreeCAD")
    circle_factory = cast(
        "Callable[[object, object, float], object]",
        getattr(part_module, "Circle"),
    )
    arc_factory = cast(
        "Callable[[object, float, float], object]",
        getattr(part_module, "ArcOfCircle"),
    )
    vector_factory = cast(
        "Callable[[float, float, float], object]",
        getattr(app_module, "Vector"),
    )

    sx, sy = float(start.x), float(start.y)
    ex, ey = float(end.x), float(end.y)
    mx, my = float(midpoint.x), float(midpoint.y)
    start_sq = sx * sx + sy * sy
    end_sq = ex * ex + ey * ey
    middle_sq = mx * mx + my * my
    determinant = 2.0 * (sx * (ey - my) + ex * (my - sy) + mx * (sy - ey))
    if abs(determinant) <= 1e-9:
        msg = "tunic armhole points are collinear; cannot construct an arc"
        raise RuntimeError(msg)

    center_x = (start_sq * (ey - my) + end_sq * (my - sy) + middle_sq * (sy - ey)) / determinant
    center_y = (start_sq * (mx - ex) + end_sq * (sx - mx) + middle_sq * (ex - sx)) / determinant
    radius = math.hypot(sx - center_x, sy - center_y)
    if not math.isfinite(radius) or radius <= 1e-9:
        msg = "tunic armhole circle has an invalid radius"
        raise RuntimeError(msg)

    def curve_value(curve: object, parameter_value: float) -> _Point2D:
        """Evaluate one native curve parameter as a planar point.

        Args:
            curve: Native circle or arc exposed by the Part module.
            parameter_value: Native curve parameter to evaluate.

        Returns:
            Evaluated coordinates with x and y properties.

        Raises:
            RuntimeError: If the native curve offers no parameter evaluator.
        """
        getter = getattr(curve, "valueAt", None)
        if not callable(getter):
            getter = getattr(curve, "value", None)
        if not callable(getter):
            msg = "tunic armhole curve has no native parameter evaluator"
            raise RuntimeError(msg)
        return cast("_Point2D", getter(float(parameter_value)))

    tau = 2.0 * math.pi
    selected: tuple[object, float, float, float, float] | None = None
    for normal_z in (1.0, -1.0):
        circle = circle_factory(
            vector_factory(center_x, center_y, 0.0),
            vector_factory(0.0, 0.0, normal_z),
            radius,
        )
        # Derive parameters from the native circle basis instead of assuming
        # which global direction its X axis uses for either normal orientation.
        zero_point = curve_value(circle, 0.0)
        quarter_point = curve_value(circle, math.pi / 2.0)
        axis_x = (
            (float(zero_point.x) - center_x) / radius,
            (float(zero_point.y) - center_y) / radius,
        )
        axis_y = (
            (float(quarter_point.x) - center_x) / radius,
            (float(quarter_point.y) - center_y) / radius,
        )

        def parameter(
            point_x: float,
            point_y: float,
            axis_x: tuple[float, float] = axis_x,
            axis_y: tuple[float, float] = axis_y,
        ) -> float:
            """Compute a point's native angular coordinate in the chosen basis.

            Args:
                point_x: Authored point x coordinate in millimeters.
                point_y: Authored point y coordinate in millimeters.
                axis_x: Unit x axis derived from the native circle.
                axis_y: Unit y axis derived from the native circle.

            Returns:
                Angle normalized to the interval from zero to one full turn.
            """
            dx = point_x - center_x
            dy = point_y - center_y
            return (
                math.atan2(
                    dx * axis_y[0] + dy * axis_y[1],
                    dx * axis_x[0] + dy * axis_x[1],
                )
                % tau
            )

        start_angle = parameter(sx, sy)
        end_angle = parameter(ex, ey)
        middle_angle = parameter(mx, my)
        sweep = (end_angle - start_angle) % tau
        middle_sweep = (middle_angle - start_angle) % tau
        if sweep > 1e-9 and middle_sweep <= sweep + 1e-9:
            selected = (circle, normal_z, start_angle, sweep, middle_sweep)
            break

    if selected is None:
        msg = "tunic armhole points do not define a consistent circular sweep"
        raise RuntimeError(msg)
    circle, normal_z, start_angle, sweep, middle_sweep = selected
    if sweep >= math.pi:
        raise RuntimeError(
            "tunic armhole through-point selects a major arc: sweep-rad=%.6f" % sweep
        )

    arc = arc_factory(circle, start_angle, start_angle + sweep)
    checks = (
        ("start", start, start_angle),
        ("end", end, start_angle + sweep),
        ("midpoint", midpoint, start_angle + middle_sweep),
    )
    for role, expected, parameter_value in checks:
        actual = curve_value(arc, parameter_value)
        error = math.hypot(float(actual.x) - float(expected.x), float(actual.y) - float(expected.y))
        if error > 1e-5:
            raise RuntimeError(
                "tunic armhole arc lost authored %s: error-mm=%.6f "
                "normal-z=%.0f expected=(%.4f,%.4f) actual=(%.4f,%.4f)"
                % (
                    role,
                    error,
                    normal_z,
                    float(expected.x),
                    float(expected.y),
                    float(actual.x),
                    float(actual.y),
                )
            )
    return arc


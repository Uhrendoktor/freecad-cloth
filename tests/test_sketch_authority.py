# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for Sketcher-authoritative pattern boundaries and sampling."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import cast

import pytest

import freecad_cloth.pattern.SketchAuthority as sketch_authority
from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR
from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.sewing.SeamGraph import SeamGraph

_EXPECTED_LINE_BOUNDARY_COUNT = 4
_EXPECTED_CURVE_SAMPLE_COUNT = 32
_CLOSED_CURVE_ENDPOINT_TOLERANCE = 1e-7


class Point:
    """Minimal three-dimensional point used by fake native geometry."""

    x: float
    y: float
    z: float

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        """Create a point with millimetre coordinates.

        Args:
            x: Horizontal coordinate.
            y: Vertical coordinate.
            z: Depth coordinate, defaulting to the pattern plane.
        """
        self.x = x
        self.y = y
        self.z = z


class LineSegment:
    """Provide the endpoint interface exposed by a native Sketcher line."""

    StartPoint: Point
    EndPoint: Point

    def __init__(self, start: tuple[float, ...], end: tuple[float, ...]) -> None:
        """Create a fake line from two coordinate tuples.

        Args:
            start: Coordinates of the first endpoint.
            end: Coordinates of the second endpoint.
        """
        self.StartPoint = _point_from_coordinates(start)
        self.EndPoint = _point_from_coordinates(end)


class Sketch:
    """Contain a sequence of fake native geometry objects."""

    Geometry: list[object]

    def __init__(self, geometry: Sequence[object]) -> None:
        """Store geometry in the order supplied by the test.

        Args:
            geometry: Native-like segments exposed through the Geometry field.
        """
        self.Geometry = list(geometry)


class NativeCurve:
    """Provide the parameter and evaluator interface of a native curve."""

    FirstParameter: float
    LastParameter: float

    def __init__(
        self,
        first_parameter: float,
        last_parameter: float,
        evaluator: Callable[[float], Point],
    ) -> None:
        """Create a curve-shaped test double.

        Args:
            first_parameter: First supported curve parameter.
            last_parameter: Last supported curve parameter.
            evaluator: Function mapping a parameter to a three-dimensional point.
        """
        self.FirstParameter = first_parameter
        self.LastParameter = last_parameter
        setattr(self, "valueAt", evaluator)


def _point_from_coordinates(coordinates: tuple[float, ...]) -> Point:
    """Create a fake point from a two- or three-coordinate tuple.

    Args:
        coordinates: Point coordinates, with optional depth.

    Returns:
        A point whose omitted depth coordinate is zero.
    """
    z = coordinates[2] if len(coordinates) > 2 else 0.0
    return Point(coordinates[0], coordinates[1], z)


def test_sketch_authority_outline_preserves_intermediate_curve_samples() -> None:
    """Ensure authored intermediate arc points remain in the derived outline."""
    piece_ir = SimpleNamespace(
        boundaries=(
            BoundaryIR("front:hem", "line", ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))),
            BoundaryIR(
                "front:armhole",
                "arc",
                (
                    (10.0, 0.0, 0.0),
                    (11.0, 2.0, 0.0),
                    (11.5, 4.0, 0.0),
                    (10.0, 6.0, 0.0),
                ),
                (0.0, 1.0),
            ),
            BoundaryIR("front:neckline", "line", ((10.0, 6.0, 0.0), (0.0, 6.0, 0.0))),
            BoundaryIR("front:left-side", "line", ((0.0, 6.0, 0.0), (0.0, 0.0, 0.0))),
        )
    )
    sampled_outline = cast(
        Callable[[object], list[tuple[float, float]]],
        getattr(sketch_authority, "_sampled_outline"),
    )

    require(
        condition=sampled_outline(piece_ir)
        == [
            (0.0, 0.0),
            (10.0, 0.0),
            (11.0, 2.0),
            (11.5, 4.0),
            (10.0, 6.0),
            (0.0, 6.0),
        ],
        message="Sketch-authoritative outlines must retain intermediate authored curve samples.",
    )


def test_pattern_ir_accepts_fake_sketcher_lines_in_shuffled_insertion_order() -> None:
    """Ensure unordered native lines become a consistently ordered closed boundary."""
    piece = PatternPiece(
        "Front",
        [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)],
        id="front",
    )
    graph = SeamGraph()
    graph.add_piece(piece)
    sketch = Sketch(
        (
            LineSegment((100.0, 60.0), (0.0, 60.0)),
            LineSegment((0.0, 0.0), (100.0, 0.0)),
            LineSegment((0.0, 60.0), (0.0, 0.0)),
            LineSegment((100.0, 0.0), (100.0, 60.0)),
        )
    )

    result = PatternIR.from_sketches(graph, {"front": sketch})
    boundaries = result.piece("front").boundaries
    require(
        condition=len(boundaries) == _EXPECTED_LINE_BOUNDARY_COUNT,
        message="A rectangular sketch must produce four ordered boundaries.",
    )
    require(
        condition=boundaries[0].id == "front:edge:0",
        message="The first ordered boundary must retain the canonical edge identifier.",
    )
    require(
        condition=all(boundary.kind == "line" for boundary in boundaries),
        message="All native line segments must remain line boundaries.",
    )
    for current, following in zip(boundaries, boundaries[1:] + boundaries[:1], strict=False):
        require(
            condition=current.samples[-1] == following.samples[0],
            message="Adjacent ordered line boundaries must share an endpoint.",
        )


def test_pattern_ir_accepts_single_closed_native_curve_as_a_pattern_boundary() -> None:
    """Ensure a single closed native curve is sampled as a complete boundary."""
    piece = PatternPiece(
        "Circle",
        [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)],
        id="circle",
    )
    graph = SeamGraph()
    graph.add_piece(piece)

    def evaluate_circle(parameter: float) -> Point:
        """Return a point on the fixture circle.

        Args:
            parameter: Angular position in radians.

        Returns:
            The matching point in the pattern plane.
        """
        return Point(
            50.0 + 50.0 * math.cos(parameter),
            50.0 + 50.0 * math.sin(parameter),
        )

    curve = NativeCurve(0.0, 2.0 * math.pi, evaluate_circle)
    sketch = Sketch((curve,))

    result = PatternIR.from_sketches(
        graph,
        {"circle": sketch},
        curve_samples=_EXPECTED_CURVE_SAMPLE_COUNT,
    )
    boundary = result.piece("circle").boundaries[0]
    require(
        condition=boundary.kind == "curve",
        message="A single native circular curve must remain a curve boundary.",
    )
    require(
        condition=len(boundary.samples) == _EXPECTED_CURVE_SAMPLE_COUNT,
        message="A closed native curve must preserve the requested sample count.",
    )
    require(
        condition=(
            math.dist(boundary.samples[0], boundary.samples[-1])
            <= _CLOSED_CURVE_ENDPOINT_TOLERANCE
        ),
        message="The first and last samples of a closed curve must coincide within tolerance.",
    )


def test_pattern_ir_rejects_open_single_curve_as_a_pattern_boundary() -> None:
    """Ensure an open single native curve cannot be treated as a closed pattern."""
    piece = PatternPiece(
        "Open",
        [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)],
        id="open",
    )
    graph = SeamGraph()
    graph.add_piece(piece)

    def evaluate_open_curve(parameter: float) -> Point:
        """Return a point on the fixture's non-closing curve.

        Args:
            parameter: Position along the curve.

        Returns:
            The corresponding point in the pattern plane.
        """
        return Point(100.0 * parameter, 40.0 * parameter)

    curve = NativeCurve(0.0, 1.0, evaluate_open_curve)
    sketch = Sketch((curve,))

    with pytest.raises(ValueError, match="single boundary does not close"):
        PatternIR.from_sketches(graph, {"open": sketch})

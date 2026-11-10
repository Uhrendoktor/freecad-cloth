# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression coverage for solver-neutral PatternIR and native Sketcher boundaries."""

import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar, TypedDict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import LineSegment as GeometryLineSegment
from freecad_cloth.pattern.PatternGeometry import ParametricPattern, QuadraticBezier, rectangle
from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR, Point3
from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    capture_edge_reference,
    resolve_edge_reference,
    resolve_edge_reference_status,
)
from freecad_cloth.sewing.SeamGraph import SeamGraph

Point2 = tuple[float, float]
CURVE_SAMPLE_COUNT = 9
NATIVE_CURVE_SAMPLE_COUNT = 7
STRAIGHT_EDGE_LENGTH = 10.0
NATIVE_CURVE_EPSILON = 1e-12


def _graph() -> SeamGraph:
    """Build two square panels joined by a seam with mixed edge-reference forms.

    Returns:
        Validated seam graph used by the semantic-edge conversion tests.
    """
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (20, 0), (20, 20), (0, 20)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (20, 0), (20, 20), (0, 20)], id="back"))
    graph.add_seam(
        Seam("front", 1, "back", "edge:3", id="side", reversed_b=True, alignment="uniform")
    )
    return graph


def test_integer_and_string_edges_become_semantic_ids() -> None:
    """Resolve indexed and named seam edges to stable semantic IDs."""
    ir = PatternIR.from_graph(_graph())
    seam = ir.seams[0]
    assert seam.edge_a == "edge:1"
    assert seam.edge_b == "edge:3"
    assert seam.reversed_b is True
    assert seam.alignment == "uniform"
    ir.validate()


def test_richer_curve_geometry_survives_in_the_ir() -> None:
    """Keep curved pattern samples and their endpoints in the solver-neutral IR."""
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    graph.add_seam(Seam("front", "curve", "back", "bottom", id="curve-seam"))
    geometry = {
        "front": ParametricPattern(
            [
                QuadraticBezier("curve", (0, 0), (5, 8), (10, 0)),
                GeometryLineSegment("line-a", (10, 0), (0, 10)),
                GeometryLineSegment("line-b", (0, 10), (0, 0)),
            ]
        ),
        "back": rectangle(10, 10),
    }
    ir = PatternIR.from_graph(graph, geometry, curve_samples=CURVE_SAMPLE_COUNT)
    boundary = ir.boundary("front", "curve")
    assert boundary.kind == "curve"
    assert len(boundary.samples) == CURVE_SAMPLE_COUNT
    assert boundary.samples[0] == (0.0, 0.0, 0.0)
    assert boundary.samples[-1] == (STRAIGHT_EDGE_LENGTH, 0.0, 0.0)
    assert boundary.length > STRAIGHT_EDGE_LENGTH


class _Point:
    """Minimal native-vector stand-in exposing FreeCAD's lowercase coordinates."""

    x: float
    y: float
    z: float

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        """Store a three-dimensional point used by the Sketcher geometry fixtures.

        Args:
            x: Horizontal coordinate of the fixture point.
            y: Vertical coordinate of the fixture point.
            z: Depth coordinate, defaulting to the sketch plane.
        """
        self.x = x
        self.y = y
        self.z = z


class LineSegment:
    """Straight native-edge stand-in with FreeCAD's endpoint attributes."""

    StartPoint: _Point
    EndPoint: _Point

    def __init__(self, start: Point2, end: Point2) -> None:
        """Create a straight edge from two two-dimensional endpoint coordinates.

        Args:
            start: First endpoint in sketch coordinates.
            end: Second endpoint in sketch coordinates.
        """
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _NativeCurve:
    """Curved Sketcher stand-in supporting native parameterized point evaluation."""

    FirstParameter: ClassVar[float] = 2.0
    LastParameter: ClassVar[float] = 4.0

    def __init__(self, start: Point2, end: Point2, bend: float = 0.0) -> None:
        """Store curve endpoints and a perpendicular midpoint displacement.

        Args:
            start: Native curve start point in sketch coordinates.
            end: Native curve end point in sketch coordinates.
            bend: Signed perpendicular displacement at the curve midpoint.
        """
        self._start = start
        self._end = end
        self._bend = bend

    def value_at(self, parameter: float) -> _Point:
        """Evaluate a bent curve at a native parameter within its parameter range.

        Args:
            parameter: Native curve parameter between the stored first and last values.

        Returns:
            Evaluated point in sketch coordinates.
        """
        t = (parameter - self.FirstParameter) / (self.LastParameter - self.FirstParameter)
        x = self._start[0] + (self._end[0] - self._start[0]) * t
        y = self._start[1] + (self._end[1] - self._start[1]) * t
        dx = self._end[0] - self._start[0]
        dy = self._end[1] - self._start[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length > NATIVE_CURVE_EPSILON:
            offset = self._bend * math.sin(math.pi * t) / length
            x -= dy * offset
            y += dx * offset
        return _Point(x, y)

# Keep FreeCAD's native camel-case curve API available to the adapter.
setattr(_NativeCurve, "valueAt", _NativeCurve.value_at)


class ArcOfCircle(_NativeCurve):
    """Arc fixture identifying the native circle-arc curve category."""


class BSplineCurve(_NativeCurve):
    """B-spline fixture identifying the native spline curve category."""


class BezierCurve(_NativeCurve):
    """Bezier fixture identifying the native Bezier curve category."""


class _Sketch:
    """Sketcher-like fixture exposing native geometry and semantic edge identities."""

    Geometry: Sequence[object]
    SemanticEdgeIds: Sequence[str]

    def __init__(self, geometry: Sequence[object], semantic_ids: Sequence[str]) -> None:
        """Retain the ordered geometry and optional persistent IDs for each edge.

        Args:
            geometry: Native-style edge objects in sketch insertion order.
            semantic_ids: Persistent edge identifiers parallel to the geometry sequence.
        """
        self.Geometry = geometry
        self.SemanticEdgeIds = semantic_ids

    @staticmethod
    def get_construction(_index: int) -> bool:
        """Mark every fixture geometry element as a real boundary edge.

        Args:
            _index: Geometry index inspected by the native adapter.

        Returns:
            False because this fixture contains no construction geometry.
        """
        return False

# Preserve the camel-case name exposed by a native Sketcher object.
setattr(_Sketch, "getConstruction", staticmethod(_Sketch.get_construction))


def _sketch_graph(curve: _NativeCurve, edge_id: str) -> tuple[SeamGraph, _Sketch]:
    """Pair a curved edge fixture with two panels and a seam referencing that edge.

    Args:
        curve: Native-style curved geometry to place in the first panel sketch.
        edge_id: Semantic identifier assigned to the curved edge.

    Returns:
        Seam graph and matching sketch fixture for the first panel.
    """
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    graph.add_seam(Seam("piece", edge_id, "other", "other:edge:0", id="seam"))
    geometry: tuple[object, ...] = (
        LineSegment((0, 0), (10, 0)),
        curve,
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 10), (0, 0)),
    )
    sketch = _Sketch(
        geometry,
        ("piece:edge:0", edge_id, "piece:edge:2", "piece:edge:3"),
    )
    return graph, sketch


def _other_sketch() -> _Sketch:
    """Build a square companion sketch with stable IDs for each of its four edges.

    Returns:
        Sketch fixture for the second square panel.
    """
    return _Sketch(
        (
            LineSegment((0, 0), (10, 0)),
            LineSegment((10, 0), (10, 10)),
            LineSegment((10, 10), (0, 10)),
            LineSegment((0, 10), (0, 0)),
        ),
        ("other:edge:0", "other:edge:1", "other:edge:2", "other:edge:3"),
    )


def test_native_sketch_curve_kinds_are_preserved() -> None:
    """Preserve native curve classes, parameter intervals, and deterministic samples."""
    native_types: tuple[tuple[type[_NativeCurve], str], ...] = (
        (ArcOfCircle, "arc"),
        (BSplineCurve, "bspline"),
        (BezierCurve, "bezier"),
    )
    for native_type, expected_kind in native_types:
        curve = native_type((10, 0), (10, 10))
        graph, sketch = _sketch_graph(curve, "piece:curved")
        ir = PatternIR.from_sketches(
            graph,
            {"piece": sketch, "other": _other_sketch()},
            curve_samples=NATIVE_CURVE_SAMPLE_COUNT,
        )
        boundary = ir.boundary("piece", "piece:curved")
        assert boundary.kind == expected_kind
        assert boundary.parameter_range == (2.0, 4.0)
        assert len(boundary.samples) == NATIVE_CURVE_SAMPLE_COUNT
        assert boundary.samples[0] == (10.0, 0.0, 0.0)
        assert boundary.samples[-1] == (10.0, 10.0, 0.0)


class _PatternIREdgeRecord(TypedDict):
    """Typed edge snapshot passed to the persistent semantic-reference adapter."""

    piece_id: str
    id: str
    points: tuple[Point2, Point2]
    provenance: tuple[str, str, str, tuple[float, float], tuple[Point3, ...]]


def _pattern_ir_edge_record(boundary: BoundaryIR) -> _PatternIREdgeRecord:
    """Project a sampled IR boundary into the edge-reference adapter's input shape.

    Args:
        boundary: Sampled IR boundary whose native provenance must be persisted.

    Returns:
        Typed edge record containing its semantic identity, endpoints, and provenance.
    """
    samples = boundary.samples
    return {
        "piece_id": "piece",
        "id": boundary.id,
        "points": (
            (samples[0][0], samples[0][1]),
            (samples[-1][0], samples[-1][1]),
        ),
        "provenance": (
            "PatternIR",
            "Sketcher",
            boundary.kind,
            boundary.parameter_range,
            samples,
        ),
    }


def test_native_curve_shape_change_with_same_endpoints_is_changed_reference() -> None:
    """Reject changed native curve geometry even when its endpoints remain unchanged."""
    first_curve = ArcOfCircle((10, 0), (10, 10), bend=4.0)
    second_curve = ArcOfCircle((10, 0), (10, 10), bend=7.0)
    first_graph, first_sketch = _sketch_graph(first_curve, "piece:curved")
    second_graph, second_sketch = _sketch_graph(second_curve, "piece:curved")
    first_ir = PatternIR.from_sketches(
        first_graph,
        {"piece": first_sketch, "other": _other_sketch()},
        curve_samples=CURVE_SAMPLE_COUNT,
    )
    second_ir = PatternIR.from_sketches(
        second_graph,
        {"piece": second_sketch, "other": _other_sketch()},
        curve_samples=CURVE_SAMPLE_COUNT,
    )
    first_edge = _pattern_ir_edge_record(first_ir.boundary("piece", "piece:curved"))
    second_edge = _pattern_ir_edge_record(second_ir.boundary("piece", "piece:curved"))
    assert first_edge["points"] == second_edge["points"]
    assert first_edge["provenance"] != second_edge["provenance"]
    reference = capture_edge_reference(
        "piece", first_edge["id"], first_edge["points"], first_edge["provenance"]
    )
    with pytest.raises(ChangedEdgeReference):
        resolve_edge_reference(reference, [second_edge])
    assert resolve_edge_reference_status(reference, [second_edge]) == (False, "changed")


def test_shuffled_sketch_geometry_resolves_by_endpoint_connectivity() -> None:
    """Order a shuffled native sketch from its endpoint topology and semantic IDs."""
    curve = ArcOfCircle((10, 0), (10, 10))
    graph, _ = _sketch_graph(curve, "piece:curve")
    shuffled = _Sketch(
        (
            LineSegment((10, 10), (0, 10)),
            LineSegment((0, 0), (10, 0)),
            curve,
            LineSegment((0, 10), (0, 0)),
        ),
        ("piece:edge:2", "piece:edge:0", "piece:curve", "piece:edge:3"),
    )
    ir = PatternIR.from_sketches(graph, {"piece": shuffled, "other": _other_sketch()})
    assert [edge.id for edge in ir.pieces[0].boundaries] == [
        "piece:curve",
        "piece:edge:2",
        "piece:edge:3",
        "piece:edge:0",
    ]
    assert ir.seams[0].edge_a == "piece:curve"
    assert ir.boundary("piece", "piece:edge:2").samples[0] == (10.0, 10.0, 0.0)


def test_shuffled_line_sketch_geometry_is_deterministic() -> None:
    """Keep line-only boundary ordering deterministic when geometry insertion order changes."""
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch(
        (
            LineSegment((10, 10), (0, 10)),
            LineSegment((0, 10), (0, 0)),
            LineSegment((0, 0), (10, 0)),
            LineSegment((10, 0), (10, 10)),
        ),
        ("piece:edge:2", "piece:edge:3", "piece:edge:0", "piece:edge:1"),
    )
    graph.add_seam(Seam("piece", 1, "other", 0, id="seam"))
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    assert [edge.id for edge in ir.pieces[0].boundaries] == [
        "piece:edge:0",
        "piece:edge:3",
        "piece:edge:2",
        "piece:edge:1",
    ]
    assert ir.seams[0].edge_a == "piece:edge:3"


def test_open_sketch_boundary_fails_with_diagnostic() -> None:
    """Reject a Sketcher boundary whose edges leave an unmatched endpoint."""
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch(
        (
            LineSegment((0, 0), (10, 0)),
            LineSegment((10, 0), (10, 10)),
            LineSegment((10, 10), (0, 10)),
        ),
        ("piece:edge:0", "piece:edge:1", "piece:edge:2"),
    )
    with pytest.raises(ValueError, match="open"):
        PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})


def test_ambiguous_sketch_boundary_fails_with_diagnostic() -> None:
    """Reject a Sketcher endpoint shared by more than two boundary edges."""
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch(
        (
            LineSegment((0, 0), (10, 0)),
            LineSegment((10, 0), (10, 10)),
            LineSegment((10, 10), (0, 10)),
            LineSegment((0, 10), (0, 0)),
            LineSegment((0, 0), (10, 10)),
        ),
        ("piece:edge:0", "piece:edge:1", "piece:edge:2", "piece:edge:3", "piece:diagonal"),
    )
    with pytest.raises(ValueError, match="ambiguous"):
        PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})


def test_disconnected_sketch_boundaries_fail_with_diagnostic() -> None:
    """Reject multiple closed sketch loops instead of treating them as one boundary."""
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    sketch = _Sketch(
        (
            LineSegment((0, 0), (1, 0)),
            LineSegment((1, 0), (0.5, 1)),
            LineSegment((0.5, 1), (0, 0)),
            LineSegment((20, 0), (21, 0)),
            LineSegment((21, 0), (20.5, 1)),
            LineSegment((20.5, 1), (20, 0)),
        ),
        ("piece:a", "piece:b", "piece:c", "piece:d", "piece:e", "piece:f"),
    )
    with pytest.raises(ValueError, match="disconnected"):
        PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})


def test_sketch_semantic_ids_survive_raw_integer_seam_resolution() -> None:
    """Resolve an integer seam edge through its explicit native Sketcher semantic ID."""
    curve = ArcOfCircle((10, 0), (10, 10))
    graph = SeamGraph()
    graph.add_piece(PatternPiece("piece", [(0, 0), (10, 0), (10, 10), (0, 10)], id="piece"))
    graph.add_piece(PatternPiece("other", [(0, 0), (10, 0), (10, 10), (0, 10)], id="other"))
    graph.add_seam(Seam("piece", 1, "other", 0, id="seam"))
    sketch = _Sketch(
        (
            LineSegment((0, 0), (10, 0)),
            curve,
            LineSegment((10, 10), (0, 10)),
            LineSegment((0, 10), (0, 0)),
        ),
        ("piece:edge:0", "piece:curve", "piece:edge:2", "piece:edge:3"),
    )
    ir = PatternIR.from_sketches(graph, {"piece": sketch, "other": _other_sketch()})
    assert ir.seams[0].edge_a == "piece:curve"
    assert ir.boundary("piece", "piece:curve").kind == "arc"


def test_unresolvable_string_reference_fails_closed() -> None:
    """Reject a persisted seam string that does not name a real panel boundary."""
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    graph.add_seam(Seam("front", "missing", "back", 0, id="bad"))
    with pytest.raises(ValueError, match="unknown boundary"):
        PatternIR.from_graph(graph)


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    sys.stdout.write("PatternIR tests passed\n")

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Small, native-shape-compatible Sketcher fixtures shared by regression tests."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace


class _SketchVector:
    """Three-dimensional point value exposed by the Sketcher edge test adapter."""

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        """Create a coordinate with the same interface as a FreeCAD vector."""
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _SketchLineEdge:
    """Straight Sketcher edge exposing a native shape-discretization API."""

    def __init__(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        """Store the local segment endpoints."""
        self._points = (_SketchVector(*start), _SketchVector(*end))

    def toShape(self) -> _SketchLineEdge:
        """Return the edge shape consumed by the sewing adapters."""
        return self

    def discretize(self, count: int) -> tuple[_SketchVector, ...]:
        """Return the ordered endpoints of this straight edge."""
        del count
        return self._points


def sketcher_pattern_piece(
    piece_id: str,
    points: Sequence[tuple[float, float]],
    *,
    placement: SimpleNamespace | None = None,
) -> SimpleNamespace:
    """Build a Sketcher-authoritative PatternPiece with one closed native edge loop.

    Args:
        piece_id: Stable identity used to derive semantic edge identifiers.
        points: Ordered two-dimensional loop vertices; the final edge closes to the first.
        placement: Optional FreeCAD-like placement adapter used by edge queries.

    Returns:
        A PatternPiece stand-in with native Sketcher geometry and stable semantic IDs.
    """
    vertices = tuple((float(x), float(y)) for x, y in points)
    geometry = tuple(
        _SketchLineEdge(start, vertices[(index + 1) % len(vertices)])
        for index, start in enumerate(vertices)
    )
    sketch = SimpleNamespace(
        Geometry=geometry,
        SemanticEdgeIds=tuple(f"{piece_id}:edge:{index}" for index in range(len(geometry))),
        Placement=placement,
    )
    return SimpleNamespace(
        Name=piece_id.replace("-", "_"),
        Label=piece_id,
        PatternType="PatternPiece",
        PieceId=piece_id,
        GeometryAuthority="Sketcher",
        GeometryMode="Sketch",
        Sketch=sketch,
        Placement=placement,
        SeamAllowance=0.0,
        GrainlineAngle=0.0,
        Width=max(x for x, _ in vertices) - min(x for x, _ in vertices),
        Height=max(y for _, y in vertices) - min(y for _, y in vertices),
    )

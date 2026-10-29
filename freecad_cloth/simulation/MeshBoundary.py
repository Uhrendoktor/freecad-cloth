# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared semantic-boundary mapping and GEOS polyline projection for meshes."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

from shapely.geometry import LineString, Point as ShapelyPoint

from freecad_cloth.pattern.PatternIR import PieceIR

if TYPE_CHECKING:
    from freecad_cloth.pattern.PatternMesh import TriangleMesh


@lru_cache(maxsize=256)
def _polyline_geometry(polyline: tuple[tuple[float, float], ...]) -> LineString:
    """Cache the GEOS representation used for repeated vertex projections.

    Args:
        polyline: Authored two-dimensional polyline coordinates.

    Returns:
        The immutable line geometry used by projection.
    """
    return LineString(polyline)


def polyline_parameter(
    point: Sequence[float],
    polyline: Sequence[Sequence[float]],
) -> float:
    """Project a point onto a polyline using GEOS arc-length projection.

    Args:
        point: Two-dimensional point to project.
        polyline: Authored polyline samples defining the projection path.

    Returns:
        Normalized arc-length position in ``[0, 1]``. Degenerate lines and
        inputs with fewer than two points return ``0.0``.
    """
    coordinates = tuple((float(sample[0]), float(sample[1])) for sample in polyline)
    if len(coordinates) < 2:
        return 0.0
    line = _polyline_geometry(coordinates)
    if line.length <= 1e-12:
        return 0.0
    return float(
        line.project(
            ShapelyPoint(float(point[0]), float(point[1])),
            normalized=True,
        )
    )


def semantic_boundary_chains(
    mesh: TriangleMesh,
    piece_ir: PieceIR,
    *,
    source_name: str,
) -> tuple[tuple[int, ...], ...]:
    """Return ordered mesh vertex chains for canonical PatternIR boundaries.

    Args:
        mesh: Triangulated pattern mesh with semantic boundary segment IDs.
        piece_ir: Canonical PatternIR record whose boundary order is preserved.
        source_name: Diagnostic label identifying the mesh producer.

    Returns:
        One ordered sequence of mesh vertex indices per IR boundary, in the
        same order as ``piece_ir.boundaries``.

    Raises:
        ValueError: If segment provenance is missing, unknown, or disconnected.
    """
    boundary = tuple(int(index) for index in mesh.boundary_vertex_indices)
    segment_ids = tuple(str(value) for value in mesh.boundary_edge_segment_ids)
    if not segment_ids:
        msg = f"{source_name} boundary provenance is missing"
        raise ValueError(msg)
    if len(segment_ids) != len(boundary):
        msg = f"{source_name} boundary provenance length does not match boundary vertices"
        raise ValueError(msg)

    semantic_ids = tuple(str(edge.id) for edge in piece_ir.boundaries)
    edge_pairs: dict[str, list[tuple[int, int]]] = {}
    for index, segment_id in enumerate(segment_ids):
        semantic_id = next(
            (
                edge_id
                for edge_id in semantic_ids
                if segment_id == edge_id or segment_id.startswith(edge_id + "::sub::")
            ),
            None,
        )
        if semantic_id is None:
            msg = f"{source_name} boundary provenance contains an unknown semantic edge"
            raise ValueError(msg)
        pair = (boundary[index], boundary[(index + 1) % len(boundary)])
        edge_pairs.setdefault(semantic_id, []).append(pair)

    mesh_vertices = tuple(mesh.vertices)
    chains = []
    for boundary_ir in piece_ir.boundaries:
        edge_id = str(boundary_ir.id)
        pairs = edge_pairs.get(edge_id)
        if not pairs:
            msg = f"{source_name} has no boundary provenance for semantic edge {edge_id}"
            raise ValueError(msg)
        vertex_indices = {vertex for pair in pairs for vertex in pair}
        authored = tuple((float(point[0]), float(point[1])) for point in boundary_ir.samples)
        ordered = tuple(
            sorted(
                vertex_indices,
                key=lambda vertex: polyline_parameter(mesh_vertices[vertex], authored),
            )
        )
        if len(ordered) < 2:
            msg = f"{source_name} semantic edge {edge_id} has too few boundary vertices"
            raise ValueError(msg)
        actual_pairs = {frozenset(pair) for pair in pairs}
        ordered_pairs = {
            frozenset((left, right)) for left, right in zip(ordered, ordered[1:], strict=False)
        }
        if ordered_pairs != actual_pairs:
            msg = f"{source_name} semantic edge {edge_id} boundary chain is disconnected"
            raise ValueError(msg)
        chains.append(ordered)
    return tuple(chains)

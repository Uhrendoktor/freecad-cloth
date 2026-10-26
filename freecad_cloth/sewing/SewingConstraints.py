# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral sewing constraints derived from pattern seams."""

from collections.abc import Sequence
from math import hypot

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.pattern.PatternGeometry import ParametricPattern, Point, Segment
from freecad_cloth.pattern.PatternMesh import TriangleMesh
from freecad_cloth.pattern.PatternModel import EdgeRef, Seam

MINIMUM_SEAM_SAMPLES = 2


@pydantic_dataclass(frozen=True)
class SewingPatternMesh:
    """Authored pattern and its corresponding triangulated mesh."""

    pattern: ParametricPattern
    mesh: TriangleMesh


@pydantic_dataclass(frozen=True)
class Stitch:
    """One pair of mesh vertices connected by a sewing stitch."""

    vertex_a: int
    vertex_b: int
    rest_length: float = 0.0


@pydantic_dataclass(frozen=True)
class SewingConstraintSet:
    """Validated stitch links grouped by their canonical seam identifier."""

    stitches: tuple[Stitch, ...]
    seam_map: dict[str, tuple[tuple[int, int], ...]]

    def validate(self) -> None:
        """Validate all stitch links and their non-negative rest lengths.

        Raises:
            ValueError: If a stitch connects a vertex to itself or has a negative rest length.
        """
        for stitch in self.stitches:
            if stitch.vertex_a == stitch.vertex_b:
                msg = "a stitch cannot connect a vertex to itself"
                raise ValueError(msg)
            if stitch.rest_length < 0:
                msg = "stitch rest length cannot be negative"
                raise ValueError(msg)


def build_sewing_constraints(
    side_a: SewingPatternMesh,
    side_b: SewingPatternMesh,
    seam: Seam,
    samples: int = 8,
) -> SewingConstraintSet:
    """Map corresponding canonical seam samples to mesh boundary vertices.

    Args:
        side_a: First authored pattern and its triangulated mesh.
        side_b: Second authored pattern and its triangulated mesh.
        seam: Canonical seam with index or stable-ID edge references.
        samples: Number of corresponding positions sampled along the seam.

    Returns:
        Validated stitch constraints and the sampled vertex correspondence map.

    Raises:
        ValueError: If the seam, sample count, edge reference, or boundary provenance is invalid.
    """
    seam.validate()
    if samples < MINIMUM_SEAM_SAMPLES:
        msg = f"seam samples must be at least {MINIMUM_SEAM_SAMPLES}"
        raise ValueError(msg)
    if not seam.piece_a.strip() or not seam.piece_b.strip():
        msg = "seam piece names must not be empty"
        raise ValueError(msg)

    pattern_a, mesh_a = side_a.pattern, side_a.mesh
    pattern_b, mesh_b = side_b.pattern, side_b.mesh
    seg_a = _resolve_seam_segment(pattern_a, seam.edge_a, "edge_a")
    seg_b = _resolve_seam_segment(pattern_b, seam.edge_b, "edge_b")
    boundary_a = _segment_boundary_vertices(mesh_a, seg_a.id)
    boundary_b = _segment_boundary_vertices(mesh_b, seg_b.id)
    stitches: list[Stitch] = []
    pairs: list[tuple[int, int]] = []
    for index in range(samples):
        t = index / (samples - 1)
        vertex_a = _nearest_boundary_vertex(mesh_a, boundary_a, seg_a.point(t))
        vertex_b = _nearest_boundary_vertex(mesh_b, boundary_b, seg_b.point(1.0 - t))
        pair = (vertex_a, vertex_b)
        if not pairs or pairs[-1] != pair:
            pairs.append(pair)
            stitches.append(Stitch(vertex_a, vertex_b))
    key = f"{seam.piece_a}:{seam.edge_a}-{seam.piece_b}:{seam.edge_b}"
    result = SewingConstraintSet(tuple(stitches), {key: tuple(pairs)})
    result.validate()
    return result


def _resolve_seam_segment(
    pattern: ParametricPattern,
    edge_reference: EdgeRef,
    field_name: str,
) -> Segment:
    """Resolve an integer edge index or stable segment identifier.

    Args:
        pattern: Authored pattern whose ordered segments define its boundary.
        edge_reference: Integer segment position or persistent segment ID.
        field_name: Seam field name used in validation feedback.

    Returns:
        Authored segment referenced by the seam.

    Raises:
        ValueError: If the integer index or stable segment ID is absent from the pattern.
    """
    if isinstance(edge_reference, int):
        if 0 <= edge_reference < len(pattern.segments):
            return pattern.segments[edge_reference]
        msg = f"seam {field_name} is outside pattern topology"
        raise ValueError(msg)

    segment = pattern.by_id().get(edge_reference)
    if segment is None:
        msg = f"seam {field_name} references unknown segment id: {edge_reference}"
        raise ValueError(msg)
    return segment


def _segment_boundary_vertices(mesh: TriangleMesh, segment_id: str) -> tuple[int, ...]:
    """Select mesh boundary vertices belonging to one authored segment.

    Args:
        mesh: Triangulated pattern mesh with optional edge provenance.
        segment_id: Stable identifier of the authored pattern segment.

    Returns:
        Boundary vertex indices associated with the segment, in boundary order.

    Raises:
        ValueError: If supplied boundary provenance is malformed or omits the segment ID.
    """
    boundary = mesh.boundary_vertex_indices
    provenance = mesh.boundary_edge_segment_ids
    if not provenance:
        return boundary
    if len(provenance) != len(boundary):
        msg = "boundary provenance must match boundary edge count"
        raise ValueError(msg)

    selected: list[int] = []
    seen: set[int] = set()
    boundary_count = len(boundary)
    for position, edge_id in enumerate(provenance):
        if edge_id != segment_id:
            continue
        adjacent_vertices = (
            boundary[position],
            boundary[(position + 1) % boundary_count],
        )
        for vertex in adjacent_vertices:
            if vertex not in seen:
                selected.append(vertex)
                seen.add(vertex)
    if not selected:
        msg = f"mesh boundary has no vertices for seam segment id: {segment_id}"
        raise ValueError(msg)
    return tuple(selected)


def _nearest_boundary_vertex(
    mesh: TriangleMesh,
    indices: Sequence[int],
    point: Point,
) -> int:
    """Find the closest eligible boundary vertex to a sampled seam point.

    Args:
        mesh: Triangulated mesh containing the candidate vertices.
        indices: Boundary vertex indices eligible for this seam segment.
        point: Sampled two-dimensional seam position in millimetres.

    Returns:
        Index of the closest eligible mesh vertex.

    Raises:
        ValueError: If the seam segment has no eligible boundary vertices.
    """
    if not indices:
        msg = "mesh has no boundary vertices for the seam segment"
        raise ValueError(msg)
    return min(
        indices,
        key=lambda index: hypot(
            mesh.vertices[index][0] - point[0],
            mesh.vertices[index][1] - point[1],
        ),
    )

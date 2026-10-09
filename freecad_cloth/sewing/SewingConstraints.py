"""Solver-neutral sewing constraints derived from pattern seams."""
from typing import Any


from dataclasses import dataclass
from math import hypot

from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, PolylineSegment
from freecad_cloth.pattern.PatternMesh import TriangleMesh
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingCorrespondence import map_parameter


@dataclass(frozen=True)
class Stitch:
    """Public data model or service class for Stitch."""

    vertex_a: int
    vertex_b: int
    rest_length: float = 0.0


@dataclass(frozen=True)
class SewingConstraintSet:
    """Public data model or service class for SewingConstraintSet."""

    stitches: tuple[Stitch, ...]
    seam_map: dict[str, tuple[tuple[int, int], ...]]

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        for stitch in self.stitches:
            # Indices are local to different panel meshes, so equal numbers are valid.
            if stitch.vertex_a < 0 or stitch.vertex_b < 0:
                raise ValueError("stitch vertex indices cannot be negative")
            if stitch.rest_length < 0:
                raise ValueError("stitch rest length cannot be negative")


def build_sewing_constraints(
    pattern_a: ParametricPattern,
    mesh_a: TriangleMesh,
    pattern_b: ParametricPattern,
    mesh_b: TriangleMesh,
    seam: Seam,
    samples: int = 8,
) -> SewingConstraintSet:
    """Map corresponding seam samples to mesh boundary vertices."""
    seam.validate()
    if samples < 2:
        raise ValueError("seam samples must be at least 2")
    if not seam.piece_a.strip() or not seam.piece_b.strip():
        raise ValueError("seam piece names must not be empty")
    def resolve_segments(pattern: Any, edge_ref: Any, name: Any) -> tuple[Any, ...]:
        if isinstance(edge_ref, int) and not isinstance(edge_ref, bool):
            if edge_ref < 0 or edge_ref >= len(pattern.segments):
                raise ValueError("seam {} is outside pattern topology".format(name))
            return (pattern.segments[edge_ref],)
        key = str(edge_ref)
        exact = tuple(segment for segment in pattern.segments if str(segment.id) == key)
        if exact:
            return exact
        # Boundary refinement preserves an authored ID as edge::sub::N.
        matches = tuple(
            segment
            for segment in pattern.segments
            if str(segment.id).startswith(key + "::sub::")
        )
        if not matches:
            raise ValueError(
                "seam {} does not resolve to a semantic edge: {}".format(name, edge_ref)
            )
        indices = tuple(pattern.segments.index(segment) for segment in matches)
        if indices != tuple(range(indices[0], indices[0] + len(indices))):
            raise ValueError("refined semantic edge is not contiguous: {}".format(edge_ref))
        return matches

    def edge_point(segments: Any, parameter: Any) -> tuple[float, float]:
        """Evaluate an edge chain by normalized physical arc length."""
        polyline = []
        for segment in segments:
            if isinstance(segment, LineSegment):
                samples_for_segment = (segment.start, segment.end)
            elif isinstance(segment, PolylineSegment):
                samples_for_segment = segment.points
            else:
                samples_for_segment = tuple(segment.polyline(128))
            for point in samples_for_segment:
                point = (float(point[0]), float(point[1]))
                if not polyline or hypot(point[0] - polyline[-1][0], point[1] - polyline[-1][1]) > 1e-9:
                    polyline.append(point)
        if len(polyline) < 2:
            raise ValueError("seam edge chain has fewer than two distinct points")
        lengths = [0.0]
        for first, second in zip(polyline, polyline[1:], strict=False):
            lengths.append(lengths[-1] + hypot(second[0] - first[0], second[1] - first[1]))
        total = lengths[-1]
        if total <= 1e-12:
            raise ValueError("seam edge chain has zero length")
        target = min(1.0, max(0.0, float(parameter))) * total
        for index in range(1, len(polyline)):
            if target <= lengths[index] or index == len(polyline) - 1:
                span = lengths[index] - lengths[index - 1]
                local = 0.0 if span <= 1e-12 else (target - lengths[index - 1]) / span
                first, second = polyline[index - 1], polyline[index]
                return (
                    first[0] + (second[0] - first[0]) * local,
                    first[1] + (second[1] - first[1]) * local,
                )
        return polyline[-1]

    def boundary_candidates(mesh: Any, edge_id: Any) -> tuple[int, ...]:
        boundary = tuple(int(index) for index in mesh.boundary_vertex_indices)
        provenance = tuple(str(value) for value in mesh.boundary_edge_segment_ids)
        if len(boundary) < 3 or len(provenance) != len(boundary):
            raise ValueError("mesh boundary lacks complete semantic edge provenance")
        matched = tuple(
            index
            for index, identifier in enumerate(provenance)
            if identifier == str(edge_id) or identifier.startswith(str(edge_id) + "::sub::")
        )
        if not matched:
            raise ValueError("mesh has no boundary vertices for semantic edge {}".format(edge_id))
        candidates = set()
        for index in matched:
            candidates.add(boundary[index])
            candidates.add(boundary[(index + 1) % len(boundary)])
        return tuple(sorted(candidates))

    segments_a = resolve_segments(pattern_a, seam.edge_a, "edge_a")
    segments_b = resolve_segments(pattern_b, seam.edge_b, "edge_b")
    edge_id_a = str(seam.edge_a) if isinstance(seam.edge_a, str) else str(segments_a[0].id)
    edge_id_b = str(seam.edge_b) if isinstance(seam.edge_b, str) else str(segments_b[0].id)
    candidates_a = boundary_candidates(mesh_a, edge_id_a)
    candidates_b = boundary_candidates(mesh_b, edge_id_b)
    stitches: list[Stitch] = []
    pairs: list[tuple[int, int]] = []
    seen_pairs = set()
    for i in range(samples):
        local_t = i / (samples - 1)
        t_a = seam.start_a + (seam.end_a - seam.start_a) * local_t
        t_b = map_parameter(
            t_a,
            seam.start_a,
            seam.end_a,
            seam.start_b,
            seam.end_b,
            seam.reversed_b,
        )
        point_a = edge_point(segments_a, t_a)
        point_b = edge_point(segments_b, t_b)
        va = _nearest_boundary_vertex(mesh_a, candidates_a, point_a)
        vb = _nearest_boundary_vertex(mesh_b, candidates_b, point_b)
        pair = (va, vb)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            pairs.append(pair)
            stitches.append(Stitch(va, vb))
    key = "{}:{}-{}:{}".format(seam.piece_a, seam.edge_a, seam.piece_b, seam.edge_b)
    result = SewingConstraintSet(tuple(stitches), {key: tuple(pairs)})
    result.validate()
    return result


def _nearest_boundary_vertex(mesh: TriangleMesh, indices: Any, point: Any) -> int:
    if not indices:
        raise ValueError("mesh has no boundary vertices")
    return min(
        indices, key=lambda i: hypot(mesh.vertices[i][0] - point[0], mesh.vertices[i][1] - point[1])
    )

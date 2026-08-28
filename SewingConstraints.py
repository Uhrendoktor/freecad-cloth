"""Solver-neutral sewing constraints derived from pattern seams."""
from dataclasses import dataclass
from math import hypot
from typing import Dict, List, Tuple

from PatternGeometry import ParametricPattern
from PatternMesh import TriangleMesh
from PatternModel import Seam


@dataclass(frozen=True)
class Stitch:
    """A pair of cloth vertices that should be coincident."""
    vertex_a: int
    vertex_b: int
    rest_length: float = 0.0


@dataclass(frozen=True)
class SewingConstraintSet:
    stitches: Tuple[Stitch, ...]
    seam_map: Dict[str, Tuple[Tuple[int, int], ...]]

    def validate(self) -> None:
        for stitch in self.stitches:
            if stitch.vertex_a == stitch.vertex_b:
                raise ValueError("a stitch cannot connect a vertex to itself")
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
    """Map corresponding seam samples to mesh boundary vertices.

    The first implementation uses boundary samples only.  This gives the
    solver an explicit stitch graph while leaving the numerical solver free to
    subdivide, merge or replace constraints later.
    """
    seam.validate()
    if samples < 2:
        raise ValueError("seam samples must be at least 2")
    if seam.piece_a != seam.piece_b and seam.piece_a == "" or seam.piece_b == "":
        raise ValueError("seam piece names must not be empty")
    seg_a = pattern_a.by_id().get(_edge_id(pattern_a, seam.edge_a))
    seg_b = pattern_b.by_id().get(_edge_id(pattern_b, seam.edge_b))
    if seg_a is None or seg_b is None:
        raise ValueError("seam edge index is outside pattern topology")

    boundary_a = _segment_vertex_indices(pattern_a, mesh_a, seam.edge_a)
    boundary_b = _segment_vertex_indices(pattern_b, mesh_b, seam.edge_b)
    if len(boundary_a) < 2 or len(boundary_b) < 2:
        raise ValueError("seam edges need at least two mesh vertices")

    stitches: List[Stitch] = []
    pairs: List[Tuple[int, int]] = []
    for i in range(samples):
        t = i / (samples - 1)
        va = _nearest_boundary_vertex(mesh_a, boundary_a, _point_on_segment(seg_a, t))
        vb = _nearest_boundary_vertex(mesh_b, boundary_b, _point_on_segment(seg_b, 1.0 - t))
        if not pairs or pairs[-1] != (va, vb):
            pairs.append((va, vb))
            stitches.append(Stitch(va, vb, 0.0))
    result = SewingConstraintSet(tuple(stitches), {"%s:%d-%s:%d" % (seam.piece_a, seam.edge_a, seam.piece_b, seam.edge_b): tuple(pairs)})
    result.validate()
    return result


def _edge_id(pattern: ParametricPattern, index: int) -> str:
    if index < 0 or index >= len(pattern.segments):
        raise ValueError("seam edge index is outside pattern topology")
    return pattern.segments[index].id


def _point_on_segment(segment, t: float):
    return segment.point(max(0.0, min(1.0, t)))


def _segment_vertex_indices(pattern: ParametricPattern, mesh: TriangleMesh, index: int) -> List[int]:
    segment = pattern.segments[index]
    a, b = segment.point(0.0), segment.point(1.0)
    result = []
    for vertex_index in mesh.boundary_vertex_indices:
        p = mesh.vertices[vertex_index]
        if _distance_to_segment(p, a, b) <= 1e-6:
            result.append(vertex_index)
    if not result:
        result = [
            _nearest_boundary_vertex(mesh, mesh.boundary_vertex_indices, a),
            _nearest_boundary_vertex(mesh, mesh.boundary_vertex_indices, b),
        ]
    return result


def _nearest_boundary_vertex(mesh, indices, point):
    return min(indices, key=lambda i: hypot(mesh.vertices[i][0] - point[0], mesh.vertices[i][1] - point[1]))


def _distance_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))

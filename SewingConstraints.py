"""Solver-neutral sewing constraints derived from pattern seams."""
from dataclasses import dataclass
from math import hypot
from typing import Dict, List, Tuple

from PatternGeometry import ParametricPattern
from PatternMesh import TriangleMesh
from PatternModel import Seam


@dataclass(frozen=True)
class Stitch:
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


def build_sewing_constraints(pattern_a: ParametricPattern, mesh_a: TriangleMesh,
                             pattern_b: ParametricPattern, mesh_b: TriangleMesh,
                             seam: Seam, samples: int = 8) -> SewingConstraintSet:
    """Map corresponding seam samples to mesh boundary vertices."""
    seam.validate()
    if samples < 2:
        raise ValueError("seam samples must be at least 2")
    if not seam.piece_a.strip() or not seam.piece_b.strip():
        raise ValueError("seam piece names must not be empty")
    if seam.edge_a < 0 or seam.edge_a >= len(pattern_a.segments):
        raise ValueError("seam edge_a is outside pattern topology")
    if seam.edge_b < 0 or seam.edge_b >= len(pattern_b.segments):
        raise ValueError("seam edge_b is outside pattern topology")
    seg_a, seg_b = pattern_a.segments[seam.edge_a], pattern_b.segments[seam.edge_b]
    boundary_a = mesh_a.boundary_vertex_indices
    boundary_b = mesh_b.boundary_vertex_indices
    stitches: List[Stitch] = []
    pairs: List[Tuple[int, int]] = []
    for i in range(samples):
        t = i / (samples - 1)
        va = _nearest_boundary_vertex(mesh_a, boundary_a, seg_a.point(t))
        vb = _nearest_boundary_vertex(mesh_b, boundary_b, seg_b.point(1.0 - t))
        pair = (va, vb)
        if not pairs or pairs[-1] != pair:
            pairs.append(pair)
            stitches.append(Stitch(va, vb))
    key = "%s:%d-%s:%d" % (seam.piece_a, seam.edge_a, seam.piece_b, seam.edge_b)
    result = SewingConstraintSet(tuple(stitches), {key: tuple(pairs)})
    result.validate()
    return result


def _nearest_boundary_vertex(mesh: TriangleMesh, indices, point):
    if not indices:
        raise ValueError("mesh has no boundary vertices")
    return min(indices, key=lambda i: hypot(mesh.vertices[i][0] - point[0], mesh.vertices[i][1] - point[1]))

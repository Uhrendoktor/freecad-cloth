# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral sewing constraints derived from pattern seams."""

from math import hypot

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.pattern.PatternGeometry import ParametricPattern
from freecad_cloth.pattern.PatternMesh import TriangleMesh
from freecad_cloth.pattern.PatternModel import Seam


@pydantic_dataclass(frozen=True)
class Stitch:
    """Public data model or service class for Stitch."""

    vertex_a: int
    vertex_b: int
    rest_length: float = 0.0


@pydantic_dataclass(frozen=True)
class SewingConstraintSet:
    """Public data model or service class for SewingConstraintSet."""

    stitches: tuple[Stitch, ...]
    seam_map: dict[str, tuple[tuple[int, int], ...]]

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        for stitch in self.stitches:
            if stitch.vertex_a == stitch.vertex_b:
                msg = "a stitch cannot connect a vertex to itself"
                raise ValueError(msg)
            if stitch.rest_length < 0:
                msg = "stitch rest length cannot be negative"
                raise ValueError(msg)


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
        msg = "seam samples must be at least 2"
        raise ValueError(msg)
    if not seam.piece_a.strip() or not seam.piece_b.strip():
        msg = "seam piece names must not be empty"
        raise ValueError(msg)
    if seam.edge_a < 0 or seam.edge_a >= len(pattern_a.segments):
        msg = "seam edge_a is outside pattern topology"
        raise ValueError(msg)
    if seam.edge_b < 0 or seam.edge_b >= len(pattern_b.segments):
        msg = "seam edge_b is outside pattern topology"
        raise ValueError(msg)
    seg_a, seg_b = pattern_a.segments[seam.edge_a], pattern_b.segments[seam.edge_b]
    boundary_a = mesh_a.boundary_vertex_indices
    boundary_b = mesh_b.boundary_vertex_indices
    stitches: list[Stitch] = []
    pairs: list[tuple[int, int]] = []
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
        msg = "mesh has no boundary vertices"
        raise ValueError(msg)
    return min(
        indices, key=lambda i: hypot(mesh.vertices[i][0] - point[0], mesh.vertices[i][1] - point[1])
    )

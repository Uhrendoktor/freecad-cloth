# Copyright (C) 2026 FreeCAD Cloth contributors
"""Simulation mesh density delegated to the Triangle constrained-Delaunay library."""

from math import hypot
from typing import TypeAlias

from freecad_cloth.common.ValidationModels import SimulationMeshQualityInput
from freecad_cloth.pattern.PatternIR import PieceIR
from freecad_cloth.simulation.MeshBoundary import semantic_boundary_chains

MeshVertex: TypeAlias = tuple[float, float, float]
MeshTriangle: TypeAlias = tuple[int, int, int]
BoundaryChain: TypeAlias = tuple[int, ...]
QualityPieceMesh: TypeAlias = tuple[
    list[MeshVertex], tuple[MeshTriangle, ...], tuple[BoundaryChain, ...]
]


def quality_piece_mesh(
    piece: object,
    start_height: float,
    particle_distance: float,
    piece_ir: PieceIR | None = None,
) -> QualityPieceMesh:
    """Provide the public quality piece mesh operation."""
    inputs = SimulationMeshQualityInput.model_validate(
        {"start_height": start_height, "particle_distance": particle_distance}
    )
    start_height = inputs.start_height
    spacing = max(0.25, inputs.particle_distance)
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate
    from freecad_cloth.simulation.PatternSimulationAdapter import (
        geometry_from_piece_ir,
        resolve_piece_ir,
    )

    if piece_ir is None:
        piece_ir = resolve_piece_ir(piece)

    pattern = geometry_from_piece_ir(piece_ir)
    max_area = 0.45 * spacing * spacing
    mesh = triangulate(
        refine_linear_boundary(pattern, spacing),
        max_area=max_area,
    )
    placement = getattr(piece, "Placement", None)
    if placement is None:
        positions = [(x, y, float(start_height)) for x, y in mesh.vertices]
    else:
        import FreeCAD as App

        positions = []
        for x, y in mesh.vertices:
            point = placement.multVec(App.Vector(x, y, float(start_height)))
            positions.append((float(point.x), float(point.y), float(point.z)))

    mesh_vertices = tuple(mesh.vertices)
    chains = semantic_boundary_chains(mesh, piece_ir, source_name="quality mesh")
    for boundary_ir, ordered in zip(piece_ir.boundaries, chains, strict=True):
        edge_id = str(boundary_ir.id)
        authored = tuple((float(point[0]), float(point[1])) for point in boundary_ir.samples)
        endpoint_tolerance = 1e-7 * max(1.0, boundary_ir.length)
        first = mesh_vertices[ordered[0]]
        last = mesh_vertices[ordered[-1]]
        if (
            hypot(
                float(first[0]) - float(authored[0][0]),
                float(first[1]) - float(authored[0][1]),
            )
            > endpoint_tolerance
        ):
            msg = f"quality mesh semantic edge {edge_id} does not start at its authored vertex"
            raise ValueError(msg)
        if (
            hypot(
                float(last[0]) - float(authored[-1][0]),
                float(last[1]) - float(authored[-1][1]),
            )
            > endpoint_tolerance
        ):
            msg = f"quality mesh semantic edge {edge_id} does not end at its authored vertex"
            raise ValueError(msg)

        for left, right in zip(ordered, ordered[1:], strict=False):
            span = hypot(
                float(mesh_vertices[left][0]) - float(mesh_vertices[right][0]),
                float(mesh_vertices[left][1]) - float(mesh_vertices[right][1]),
            )
            if span > float(spacing) + endpoint_tolerance:
                msg = f"quality mesh semantic edge {edge_id} exceeds requested boundary spacing"
                raise ValueError(msg)

    return (
        positions,
        tuple(mesh.triangles),
        chains,
    )

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for canonical sewing-edge resolution and mesh provenance."""

import pytest

from freecad_cloth.pattern.PatternGeometry import ParametricPattern, rectangle
from freecad_cloth.pattern.PatternMesh import TriangleMesh, triangulate
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingConstraints import build_sewing_constraints
from tests.support.assertions import require


def _mesh_pair() -> tuple[ParametricPattern, TriangleMesh, ParametricPattern, TriangleMesh]:
    """Create two rectangular patterns and meshes with authored edge provenance.

    Returns:
        Two pattern-and-mesh pairs with matching semantic boundary identifiers.
    """
    pattern_a = rectangle(100.0, 50.0)
    pattern_b = rectangle(100.0, 50.0)
    return pattern_a, triangulate(pattern_a), pattern_b, triangulate(pattern_b)


def _vertices_on_segment(mesh: TriangleMesh, segment_id: str) -> frozenset[int]:
    """Find the boundary vertices incident to edges carrying a segment identifier.

    Args:
        mesh: Triangulated mesh with boundary edge provenance.
        segment_id: Authored segment identifier whose boundary vertices are required.

    Returns:
        Immutable set of vertices adjacent to the requested segment's boundary edges.
    """
    boundary = mesh.boundary_vertex_indices
    return frozenset(
        vertex
        for position, edge_id in enumerate(mesh.boundary_edge_segment_ids)
        if edge_id == segment_id
        for vertex in (
            boundary[position],
            boundary[(position + 1) % len(boundary)],
        )
    )


@pytest.mark.parametrize(
    ("edge_a", "edge_b", "expected_key"),
    [
        pytest.param(1, 3, "front:1-back:3", id="integer-indices"),
        pytest.param("right", "left", "front:right-back:left", id="stable-segment-ids"),
    ],
)
def test_sewing_constraints_resolve_integer_and_stable_edge_references(
    edge_a: int | str,
    edge_b: int | str,
    expected_key: str,
) -> None:
    """Build constraints for integer references and persistent segment identifiers.

    Args:
        edge_a: First seam edge represented as an index or segment ID.
        edge_b: Second seam edge represented as an index or segment ID.
        expected_key: Deterministic seam-map key for the selected edge references.
    """
    pattern_a, mesh_a, pattern_b, mesh_b = _mesh_pair()
    seam = Seam("front", edge_a, "back", edge_b, id="side")
    constraints = build_sewing_constraints(pattern_a, mesh_a, pattern_b, mesh_b, seam)

    require(
        condition=expected_key in constraints.seam_map,
        message="The seam map must preserve the canonical edge references.",
    )
    require(
        condition=bool(constraints.stitches),
        message="Valid corresponding seam edges must produce stitch constraints.",
    )
    segment_id_a = edge_a if isinstance(edge_a, str) else pattern_a.segments[edge_a].id
    segment_id_b = edge_b if isinstance(edge_b, str) else pattern_b.segments[edge_b].id
    vertices_a = _vertices_on_segment(mesh_a, segment_id_a)
    vertices_b = _vertices_on_segment(mesh_b, segment_id_b)
    require(
        condition=all(stitch.vertex_a in vertices_a for stitch in constraints.stitches),
        message="Every first-side stitch vertex must belong to the selected seam segment.",
    )
    require(
        condition=all(stitch.vertex_b in vertices_b for stitch in constraints.stitches),
        message="Every second-side stitch vertex must belong to the selected seam segment.",
    )


def test_sewing_constraints_reject_unknown_stable_segment_identifier() -> None:
    """Reject stable edge IDs that do not exist in the pattern boundary."""
    pattern_a, mesh_a, pattern_b, mesh_b = _mesh_pair()
    seam = Seam("front", "missing", "back", "left", id="invalid-edge")

    with pytest.raises(ValueError, match="seam edge_a references unknown segment id"):
        build_sewing_constraints(pattern_a, mesh_a, pattern_b, mesh_b, seam)

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Unit tests for position-level mesh collision projection."""

import numpy as np
import pytest

from freecad_cloth.avatar.MeshSanity import orient_closed_triangle_winding
from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.simulation.DrapeVisualSanity import (
    _ClosedMeshPointClassifier,
    points_inside_closed_mesh,
)
from freecad_cloth.simulation.MeshCollisionProjector import (
    MeshCollisionProjector,
    project_stitched_pairs,
)
from tests.support.closed_mesh_fixtures import CUBE_TRIANGLES


def _cube_surface() -> CollisionSurface:
    vertices = (
        (0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0),
        (100.0, 100.0, 0.0),
        (0.0, 100.0, 0.0),
        (0.0, 0.0, 100.0),
        (100.0, 0.0, 100.0),
        (100.0, 100.0, 100.0),
        (0.0, 100.0, 100.0),
    )
    triangles = CUBE_TRIANGLES
    return CollisionSurface(vertices, triangles, thickness=0.0).validate()


def _concave_l_prism_surface() -> CollisionSurface:
    """Build a closed L-shaped prism with a concave corner."""
    polygon = ((0.0, 0.0), (3.0, 0.0), (3.0, 1.0), (1.0, 1.0), (1.0, 3.0), (0.0, 3.0))
    vertices = tuple((x, y, z) for z in (0.0, 1.0) for x, y in polygon)
    cap_triangles = ((0, 1, 3), (1, 2, 3), (0, 3, 5), (3, 4, 5))
    triangles = []
    for a, b, c in cap_triangles:
        triangles.append((c, b, a))
        triangles.append((a + 6, b + 6, c + 6))
    for index in range(6):
        next_index = (index + 1) % 6
        triangles.extend(
            (
                (index, next_index, next_index + 6),
                (index, next_index + 6, index + 6),
            )
        )
    return CollisionSurface(vertices, tuple(triangles), thickness=0.0).validate()


def test_exact_nearest_surface_search_uses_bounded_triangle_candidates() -> None:
    """KD-tree bounds must retain the exhaustive nearest point while reducing faces."""
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=3, radius=50.0)
    surface = CollisionSurface(
        tuple(tuple(float(value) for value in point) for point in mesh.vertices),
        tuple(tuple(int(value) for value in face) for face in mesh.faces),
        thickness=0.0,
    ).validate()
    projector = MeshCollisionProjector(surface, clearance_mm=1.0)
    query = np.asarray((0.0, 0.0, 42.0), dtype=np.float64)

    actual_point, actual_normal = projector._nearest_surface_point(query)
    candidate_count = projector._last_nearest_candidate_count
    all_indices = np.arange(len(surface.triangles), dtype=np.int64)
    all_points, all_distances = projector._closest_points_on_triangles(query, all_indices)
    expected_point = all_points[int(np.argmin(all_distances))]

    assert np.allclose(actual_point, expected_point, atol=1e-9)
    assert np.isclose(np.linalg.norm(actual_normal), 1.0)
    assert 0 < candidate_count < len(surface.triangles) // 10


def test_cached_closed_mesh_classifier_preserves_cube_and_concave_inside_results() -> None:
    """Cached parity must classify cube and concave-prism interior/exterior points correctly."""
    surfaces_and_points = (
        (
            _cube_surface(),
            np.asarray(
                (
                    (50.0, 50.0, 50.0),
                    (-1.0, 50.0, 50.0),
                    (101.0, 50.0, 50.0),
                ),
                dtype=np.float64,
            ),
            (True, False, False),
        ),
        (
            _concave_l_prism_surface(),
            np.asarray(
                (
                    (0.5, 0.5, 0.5),
                    (2.0, 2.0, 0.5),
                    (1.5, 1.5, 0.5),
                ),
                dtype=np.float64,
            ),
            (True, False, False),
        ),
    )
    for surface, points, expected in surfaces_and_points:
        classifier = _ClosedMeshPointClassifier(surface.vertices, surface.triangles)
        first = tuple(bool(value) for value in classifier.contains_array(points))
        second = tuple(bool(value) for value in classifier.contains_array(points, chunk_size=1))

        assert first == expected
        assert second == expected


def test_cached_closed_mesh_classifier_rejects_invalid_query_arrays() -> None:
    """Cached queries still reject malformed or non-finite point arrays."""
    classifier = _ClosedMeshPointClassifier(
        _cube_surface().vertices,
        _cube_surface().triangles,
    )

    with pytest.raises(ValueError, match="shape"):
        classifier.contains_array(np.asarray((50.0, 50.0, 50.0), dtype=np.float64))
    with pytest.raises(ValueError, match="finite"):
        classifier.contains_array(np.asarray(((float("nan"), 50.0, 50.0),), dtype=np.float64))


def test_projector_escapes_concave_interior_contacts_with_exact_surface_search() -> None:
    """A local face normal at a concave corner must not push an interior point deeper."""
    surface = _concave_l_prism_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=0.1, candidate_count=2)
    point = np.asarray(((0.70232323, 0.97323232, 0.66333333),), dtype=np.float64)

    assert points_inside_closed_mesh(
        (tuple(point[0]),),
        surface.vertices,
        surface.triangles,
        prefer_trimesh=False,
    )[0]

    projected, normals = projector.project(point)

    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)
    assert not points_inside_closed_mesh(
        (tuple(projected[0]),),
        surface.vertices,
        surface.triangles,
        prefer_trimesh=False,
    )[0]


def test_projector_checks_in_bounds_points_rejected_by_local_candidate_search() -> None:
    """Closed-mesh containment must rescue an interior point outside the local search radius."""
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=1.0)
    projector._normals *= -1.0
    projector._search_radius_mm = 0.0
    point = np.asarray(((50.0, 50.0, 50.0),), dtype=np.float64)

    projected, normals = projector.project(point)

    assert np.linalg.norm(projected[0] - point[0]) > 1.0
    assert np.isclose(np.linalg.norm(normals[0]), 1.0)
    assert not points_inside_closed_mesh(
        (tuple(float(value) for value in projected[0]),),
        surface.vertices,
        surface.triangles,
        prefer_trimesh=False,
        chunk_size=1,
    )[0]


def test_projector_moves_inside_points_outside_closed_surface() -> None:
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=1.0)
    points = np.asarray(((50.0, 50.0, 50.0), (0.5, 50.0, 50.0)), dtype=np.float64)

    projected, normals = projector.project(points)

    assert np.linalg.norm(projected - points, axis=1).min() > 0.0
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)
    assert not any(
        points_inside_closed_mesh(
            (tuple(point),),
            surface.vertices,
            surface.triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )[0]
        for point in projected
    )


def test_projector_preserves_tangential_offsets_when_correcting_near_an_edge() -> None:
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    point = np.asarray(((-0.5, -0.5, 50.0),), dtype=np.float64)

    projected, normals = projector.project(point)

    assert np.isclose(np.linalg.norm(normals[0]), 1.0)
    correction = projected[0] - point[0]
    # Normal-only correction must not introduce an artificial tangential snap
    # to the closest mesh edge, which can collapse cloth triangles.
    assert np.isclose(np.linalg.norm(np.cross(correction, normals[0])), 0.0, atol=1e-8)
    assert np.isclose(np.dot(correction, normals[0]), np.linalg.norm(correction))


def test_projector_supports_reduced_preview_candidate_count() -> None:
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=2.0, candidate_count=2)
    points = np.asarray(((50.0, 50.0, 50.0), (-0.5, 50.0, 50.0)), dtype=np.float64)

    projected, normals = projector.project(points)

    assert np.all(np.isfinite(projected))
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)
    assert not any(
        points_inside_closed_mesh(
            (tuple(point),),
            surface.vertices,
            surface.triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )[0]
        for point in projected
    )


def test_projector_enforces_clearance_and_leaves_distant_points_unchanged() -> None:
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=2.0)
    points = np.asarray(
        ((-0.5, 50.0, 50.0), (-100.0, 50.0, 50.0)),
        dtype=np.float64,
    )

    projected, normals = projector.project(points)

    assert np.allclose(projected[0], (-2.0, 50.0, 50.0))
    assert np.allclose(normals[0], (-1.0, 0.0, 0.0))
    assert np.array_equal(projected[1], points[1])
    assert np.array_equal(normals[1], np.zeros(3))


def test_projector_applies_independent_clearances_to_inside_and_outside_particles() -> None:
    """A particle-specific body shell must work for both exterior and interior points."""
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=2.0)
    points = np.asarray(((-10.0, 50.0, 50.0), (10.0, 50.0, 50.0)), dtype=np.float64)

    projected, normals = projector.project(points, clearance_mm=(6.0, 14.0))

    np.testing.assert_allclose(projected, ((-6.0, 50.0, 50.0), (-14.0, 50.0, 50.0)))
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)
    assert not any(
        points_inside_closed_mesh(
            (tuple(float(value) for value in point),),
            surface.vertices,
            surface.triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )[0]
        for point in projected
    )


def test_projector_rejects_invalid_per_particle_clearance_arrays() -> None:
    """Per-particle clearance arrays must be positive, finite and match the points."""
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    points = np.asarray(((-0.5, 50.0, 50.0), (100.5, 50.0, 50.0)), dtype=np.float64)

    with pytest.raises(ValueError, match="shape"):
        projector.project(points, clearance_mm=(6.0,))
    with pytest.raises(ValueError, match="positive and finite"):
        projector.project(points, clearance_mm=(6.0, 0.0))
    with pytest.raises(ValueError, match="positive and finite"):
        projector.project(points, clearance_mm=(6.0, float("nan")))


def test_projector_skips_triangle_queries_for_points_outside_expanded_bounds() -> None:
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    # If the broad phase is skipped, this fails instead of issuing any KD-tree query.
    projector._tree = None
    points = np.asarray(
        ((-100.0, 50.0, 50.0), (50.0, 50.0, 250.0)),
        dtype=np.float64,
    )

    projected, normals = projector.project(points)

    assert np.array_equal(projected, points)
    assert np.array_equal(normals, np.zeros_like(normals))


def test_projector_handles_reversed_but_consistent_triangle_winding() -> None:
    surface = _cube_surface()
    reversed_surface = CollisionSurface(
        surface.vertices,
        tuple((a, c, b) for a, b, c in surface.triangles),
        thickness=surface.thickness,
    ).validate()
    projector = MeshCollisionProjector(reversed_surface, clearance_mm=1.0)

    projected, normals = projector.project(((50.0, 50.0, 50.0),))

    assert not points_inside_closed_mesh(
        (tuple(projected[0]),),
        reversed_surface.vertices,
        reversed_surface.triangles,
        prefer_trimesh=False,
        chunk_size=1,
    )[0]
    assert np.isclose(np.linalg.norm(normals[0]), 1.0)


def test_stitched_pair_reconciliation_closes_pair_outside_target() -> None:
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=2.0)
    points = np.asarray(
        ((-0.5, 50.0, 50.0), (100.5, 50.0, 50.0)),
        dtype=np.float64,
    )
    contact_positions, contact_normals = projector.project(points)

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
    )

    assert np.allclose(stitched_positions[0], stitched_positions[1])
    assert np.isclose(np.linalg.norm(stitched_normals[0]), 1.0)
    assert np.allclose(stitched_normals[0], stitched_normals[1])
    assert not any(
        points_inside_closed_mesh(
            (tuple(float(value) for value in point),),
            surface.vertices,
            surface.triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )[0]
        for point in stitched_positions
    )


def test_stitched_pair_reconciliation_uses_the_garment_body_clearance() -> None:
    """The shared stitch point must be projected to its owning garment shell."""
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    points = np.asarray(((-0.5, 50.0, 50.0), (-0.5, 50.0, 60.0)), dtype=np.float64)
    contact_positions, contact_normals = projector.project(points, clearance_mm=(6.0, 6.0))

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
        clearance_mm=(14.0, 14.0),
    )

    np.testing.assert_allclose(stitched_positions, ((-14.0, 50.0, 55.0),) * 2)
    assert np.allclose(np.linalg.norm(stitched_normals, axis=1), 1.0)


def test_stitched_pair_reconciliation_rejects_mixed_body_clearances() -> None:
    """A sewn component cannot straddle two distinct mannequin clearance shells."""
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    points = np.asarray(((-0.5, 50.0, 50.0), (-0.5, 50.0, 60.0)), dtype=np.float64)
    normals = np.zeros_like(points)

    with pytest.raises(ValueError, match="share one mannequin body clearance"):
        project_stitched_pairs(
            projector,
            points,
            normals,
            ((0, 1),),
            clearance_mm=(6.0, 14.0),
        )


def test_stitched_pair_reconciliation_does_not_move_a_pinned_group() -> None:
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=2.0)
    points = np.asarray(
        ((-0.5, 50.0, 50.0), (100.5, 50.0, 50.0)),
        dtype=np.float64,
    )
    contact_positions, contact_normals = projector.project(points)

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
        pinned_indices=(0,),
    )

    assert np.array_equal(stitched_positions, contact_positions)
    assert np.array_equal(stitched_normals, contact_normals)


def test_stitched_pair_reconciliation_skips_noncontacting_stitches() -> None:
    surface = _cube_surface()
    projector = MeshCollisionProjector(surface, clearance_mm=2.0)
    points = np.asarray(
        ((-100.0, 50.0, 50.0), (-90.0, 50.0, 50.0)),
        dtype=np.float64,
    )
    contact_positions, contact_normals = projector.project(points)
    assert np.array_equal(contact_normals, np.zeros_like(contact_normals))

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
    )

    assert np.array_equal(stitched_positions, contact_positions)
    assert np.array_equal(stitched_normals, contact_normals)


def test_stitched_pair_reconciliation_closes_seam_spanning_body() -> None:
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    # Both endpoints sit exactly on opposite exterior clearance shells: neither
    # individual contact query produces a normal, but the sewn pair spans the body.
    points = np.asarray(((-2.0, 50.0, 50.0), (102.0, 50.0, 50.0)), dtype=np.float64)
    contact_positions, contact_normals = projector.project(points)
    assert np.array_equal(contact_normals, np.zeros_like(contact_normals))
    assert np.linalg.norm(contact_positions[1] - contact_positions[0]) > 25.0

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
    )

    assert np.allclose(stitched_positions[0], stitched_positions[1])
    assert np.isclose(np.linalg.norm(stitched_normals[0]), 1.0)
    assert np.allclose(stitched_normals[0], stitched_normals[1])
    assert not any(
        points_inside_closed_mesh(
            (tuple(float(value) for value in point),),
            _cube_surface().vertices,
            _cube_surface().triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )[0]
        for point in stitched_positions
    )


def test_stitched_pair_reconciliation_rescues_near_shell_midpoint() -> None:
    cube = _cube_surface()
    surface = CollisionSurface(
        tuple(tuple(float(value) * 0.4 for value in vertex) for vertex in cube.vertices),
        cube.triangles,
        thickness=0.0,
    ).validate()
    projector = MeshCollisionProjector(surface, clearance_mm=5.0)
    # Both vertices are exactly on the clearance shell, but their midpoint is
    # inside the mannequin. The pair should close at the nearest exterior shell.
    points = np.asarray(((-5.0, 20.0, 20.0), (45.0, 20.0, 20.0)), dtype=np.float64)
    contact_positions, contact_normals = projector.project(points)
    assert np.array_equal(contact_normals, np.zeros_like(contact_normals))

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
    )

    assert np.allclose(stitched_positions[0], stitched_positions[1])
    assert np.isclose(np.linalg.norm(stitched_normals[0]), 1.0)
    assert np.allclose(stitched_normals[0], stitched_normals[1])
    assert not any(
        points_inside_closed_mesh(
            (tuple(float(value) for value in point) for point in stitched_positions),
            surface.vertices,
            surface.triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )
    )


def test_stitched_pair_reconciliation_closes_safe_midpoint() -> None:
    cube = _cube_surface()
    surface = CollisionSurface(
        tuple(tuple(float(value) * 0.4 for value in vertex) for vertex in cube.vertices),
        cube.triangles,
        thickness=0.0,
    ).validate()
    projector = MeshCollisionProjector(surface, clearance_mm=5.0)
    # Both endpoints are on the exterior clearance shell. The midpoint is also
    # safe, but independent projection alone leaves the residual seam open.
    points = np.asarray(((-5.0, 20.0, 15.0), (-5.0, 20.0, 25.0)), dtype=np.float64)
    contact_positions, contact_normals = projector.project(points)
    assert np.array_equal(contact_normals, np.zeros_like(contact_normals))

    stitched_positions, stitched_normals = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        ((0, 1),),
    )

    assert np.allclose(stitched_positions, ((-5.0, 20.0, 20.0), (-5.0, 20.0, 20.0)))
    assert np.array_equal(stitched_normals, np.zeros_like(stitched_normals))
    assert not any(
        points_inside_closed_mesh(
            (tuple(float(value) for value in point) for point in stitched_positions),
            surface.vertices,
            surface.triangles,
            prefer_trimesh=False,
            chunk_size=1,
        )
    )


def test_closed_mesh_orientation_repairs_local_face_winding() -> None:
    surface = _cube_surface()
    inconsistent = tuple(
        (a, c, b) if face_index == 2 else (a, b, c)
        for face_index, (a, b, c) in enumerate(surface.triangles)
    )

    oriented = orient_closed_triangle_winding(surface.vertices, inconsistent)
    projector = MeshCollisionProjector(
        CollisionSurface(surface.vertices, oriented, thickness=surface.thickness).validate(),
        clearance_mm=1.0,
    )
    projected, normals = projector.project(((50.0, 50.0, 50.0),))

    assert len(oriented) == len(inconsistent)
    assert np.isclose(np.linalg.norm(normals[0]), 1.0)
    assert not points_inside_closed_mesh(
        (tuple(float(value) for value in projected[0]),),
        surface.vertices,
        surface.triangles,
        prefer_trimesh=False,
        chunk_size=1,
    )[0]

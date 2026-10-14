"""Unit tests for position-level mesh collision projection."""

import numpy as np

from freecad_cloth.avatar.MeshSanity import orient_closed_triangle_winding
from freecad_cloth.shared.collision import CollisionSurface
from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh
from freecad_cloth.simulation.MeshCollisionProjector import (
    MeshCollisionProjector,
    project_stitched_pairs,
)


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
    triangles = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    return CollisionSurface(vertices, triangles, thickness=0.0).validate()


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

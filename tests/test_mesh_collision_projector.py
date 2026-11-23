# Copyright (C) 2026 FreeCAD Cloth contributors
"""Unit tests for position-level mesh collision projection."""

import numpy as np

from freecad_cloth.avatar.MeshSanity import orient_closed_triangle_winding
from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh
from freecad_cloth.simulation.MeshCollisionProjector import (
    MeshCollisionProjector,
    build_stitch_group_topology,
    project_stitched_pairs,
)
from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
    _pbd_stitch_group_cache_enabled,
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


def test_stitch_group_topology_builds_deterministic_transitive_components() -> None:
    """Union chains and duplicates once while omitting isolated/self-paired particles."""
    topology = build_stitch_group_topology(
        ((3, 2), (1, 2), (2, 1), (7, 7), (5, 4)),
        particle_count=9,
    )

    assert topology.particle_count == 9
    assert topology.groups == ((1, 2, 3), (4, 5))


def test_stitch_group_topology_rejects_invalid_particle_counts_and_indices() -> None:
    """Cached topology must fail closed before entering a per-step projection path."""
    for count in (-1, True, 2.5):
        try:
            build_stitch_group_topology((), particle_count=count)  # type: ignore[arg-type]
        except ValueError as exc:
            assert "particle count" in str(exc)
        else:
            raise AssertionError("invalid particle count was accepted")

    for stitches in (((-1, 0),), ((0, 3),)):
        try:
            build_stitch_group_topology(stitches, particle_count=3)
        except ValueError as exc:
            assert "stitch pair index" in str(exc)
        else:
            raise AssertionError("out-of-range stitch index was accepted")


def test_cached_stitch_topology_matches_uncached_positions_and_normals() -> None:
    """Precomputed components preserve the exact contact and seam reconciliation result."""
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    positions = np.asarray(
        (
            (-0.5, 50.0, 50.0),
            (100.5, 50.0, 50.0),
            (-2.0, 20.0, 20.0),
            (-2.0, 20.0, 24.0),
            (-100.0, 50.0, 50.0),
            (-90.0, 50.0, 50.0),
        ),
        dtype=np.float64,
    )
    contact_positions, contact_normals = projector.project(positions)
    stitches = ((0, 1), (2, 3), (4, 5))
    topology = build_stitch_group_topology(stitches, particle_count=len(positions))

    uncached = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        stitches,
        pinned_indices=(4,),
    )
    cached = project_stitched_pairs(
        projector,
        contact_positions,
        contact_normals,
        stitches,
        pinned_indices=(4,),
        stitch_topology=topology,
    )

    assert np.array_equal(cached[0], uncached[0])
    assert np.array_equal(cached[1], uncached[1])


def test_stitch_topology_particle_count_must_match_positions() -> None:
    """A cached component graph cannot be reused with a different particle layout."""
    projector = MeshCollisionProjector(_cube_surface(), clearance_mm=2.0)
    topology = build_stitch_group_topology(((0, 1),), particle_count=3)

    try:
        project_stitched_pairs(
            projector,
            np.zeros((2, 3), dtype=np.float64),
            np.zeros((2, 3), dtype=np.float64),
            ((0, 1),),
            stitch_topology=topology,
        )
    except ValueError as exc:
        assert "particle count" in str(exc)
    else:
        raise AssertionError("mismatched cached topology was accepted")


def test_stitch_group_cache_environment_defaults_on_and_validates() -> None:
    """Production uses the precomputed topology unless an audit explicitly disables it."""
    assert _pbd_stitch_group_cache_enabled({}) is True
    assert _pbd_stitch_group_cache_enabled({"CLOTH_PBD_STITCH_GROUP_CACHE": "0"}) is False
    assert _pbd_stitch_group_cache_enabled({"CLOTH_PBD_STITCH_GROUP_CACHE": "1"}) is True
    try:
        _pbd_stitch_group_cache_enabled({"CLOTH_PBD_STITCH_GROUP_CACHE": "true"})
    except ValueError as exc:
        assert "must be '0' or '1'" in str(exc)
    else:
        raise AssertionError("invalid cache toggle was accepted")

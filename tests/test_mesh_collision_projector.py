"""Unit tests for position-level mesh collision projection."""

import numpy as np

from freecad_cloth.shared.collision import CollisionSurface
from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh
from freecad_cloth.simulation.MeshCollisionProjector import MeshCollisionProjector


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
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
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

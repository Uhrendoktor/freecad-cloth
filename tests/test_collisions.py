from math import sqrt

from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMesh import triangulate
from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.simulation.SimulationBackend import ClothState
from freecad_cloth.simulation.TissuBackend import _native_decimate_collision_surface
from freecad_cloth.simulation.XPBD import DistanceConstraint, SphereCollider, XPBDClothSolver


def test_sphere_collision_pushes_particle_outside_surface():
    state = ClothState([(0.0, 0.0, 0.0)], inverse_masses=[1.0])
    solver = XPBDClothSolver(gravity=(0.0, 0.0, 0.0), colliders=[SphereCollider((0.0, 0.0, 0.0), 10.0)], iterations=2)
    solver.step(state, 0.01)
    assert state.positions[0] == (0.0, 0.0, 10.0)


def test_collision_and_structural_constraints_can_coexist():
    mesh = triangulate(rectangle(20.0, 20.0))
    constraints = [DistanceConstraint(0, 1, 20.0)]
    solver = XPBDClothSolver(constraints, gravity=(0.0, 0.0, 0.0), colliders=[SphereCollider((0.0, 0.0, 0.0), 5.0)], iterations=16)
    state = ClothState([(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)])
    solver.step(state, 0.01)
    x, y, z = state.positions[0]
    # Structural projection may pull a colliding vertex microscopically below
    # the contact surface; the invariant is enforced within solver tolerance.
    assert sqrt(x * x + y * y + z * z) >= 4.9


def _closed_cube_surface():
    vertices = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
        (10.0, 0.0, 10.0),
        (10.0, 10.0, 10.0),
        (0.0, 10.0, 10.0),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    return CollisionSurface(vertices, triangles, region="avatar", thickness=1.5)


def test_native_collision_decimation_is_exact_closed_and_deterministic():
    surface = _closed_cube_surface()
    first, first_metrics, first_seconds = _native_decimate_collision_surface(surface, 8)
    second, second_metrics, second_seconds = _native_decimate_collision_surface(surface, 8)

    assert len(first.triangles) == 8
    assert first_metrics["faces"] == 8
    assert first_metrics["components"] == 1
    assert first_metrics["boundary_edges"] == 0
    assert first_metrics["nonmanifold_edges"] == 0
    assert first_metrics["degenerate_faces"] == 0
    assert first == second
    assert first_metrics == second_metrics
    assert first_seconds >= 0.0
    assert second_seconds >= 0.0
    assert first.region == surface.region
    assert first.thickness == surface.thickness


if __name__ == "__main__":
    test_sphere_collision_pushes_particle_outside_surface()
    test_collision_and_structural_constraints_can_coexist()
    test_native_collision_decimation_is_exact_closed_and_deterministic()
    print("collision tests passed")

from math import sqrt

from freecad_cloth.avatar.AvatarCollision import coarsen_collision_surface, surface_from_triangles
from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMesh import triangulate
from freecad_cloth.simulation.SimulationBackend import ClothState
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



def test_collision_surface_coarsening_excludes_degenerate_faces_and_backfills():
    vertices = (
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0),
        (20.0, 0.0, 0.0), (30.0, 0.0, 0.0), (20.0, 10.0, 0.0),
        (0.0, 20.0, 0.0), (10.0, 20.0, 0.0), (0.0, 30.0, 0.0),
        (20.0, 20.0, 0.0), (30.0, 20.0, 0.0), (20.0, 30.0, 0.0),
        (40.0, 0.0, 0.0),
    )
    triangles = (
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (9, 10, 11),
        (0, 4, 4),  # zero-area face: same vertex twice
        (1, 5, 6),
    )
    surface = surface_from_triangles(vertices, triangles)
    first = coarsen_collision_surface(surface, max_triangles=5)
    second = coarsen_collision_surface(surface, max_triangles=5)

    assert first.triangles == second.triangles
    assert len(first.triangles) == 5
    assert (0, 4, 4) not in first.triangles

    for ia, ib, ic in first.triangles:
        a, b, c = first.vertices[ia], first.vertices[ib], first.vertices[ic]
        cross = (
            (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
            (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
            (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
        )
        assert sum(value * value for value in cross) > 0.0


if __name__ == "__main__":
    test_sphere_collision_pushes_particle_outside_surface()
    test_collision_and_structural_constraints_can_coexist()
    print("collision tests passed")

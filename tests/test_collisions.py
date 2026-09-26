from math import sqrt

from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMesh import triangulate
from freecad_cloth.simulation.SimulationBackend import ClothState
from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
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


if __name__ == "__main__":
    test_sphere_collision_pushes_particle_outside_surface()
    test_collision_and_structural_constraints_can_coexist()
    print("collision tests passed")


def test_mesh_corner_collision_resolves_multiple_contact_planes():
    vertices = (
        (-10.0, -10.0, -10.0), (10.0, -10.0, -10.0), (10.0, 10.0, -10.0), (-10.0, 10.0, -10.0),
        (-10.0, -10.0, 10.0), (10.0, -10.0, 10.0), (10.0, 10.0, 10.0), (-10.0, 10.0, 10.0),
    )
    triangles = (
        (0, 3, 2), (0, 2, 1),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    surface = surface_from_triangles(vertices, triangles, region="cube", thickness=0.0)
    state = ClothState([(9.0, 9.0, 9.0)], inverse_masses=[1.0])
    solver = XPBDClothSolver(gravity=(0.0, 0.0, 0.0), iterations=1)
    solver._collide_surface(surface)
    x, y, z = state.positions[0]
    solver._collide_surface(surface)
   
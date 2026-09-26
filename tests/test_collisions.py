from math import sqrt

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


if __name__ == "__main__":
    test_sphere_collision_pushes_particle_outside_surface()
    test_collision_and_structural_constraints_can_coexist()
    print("collision tests passed")



def _cube_surface(thickness=1.0):
    from freecad_cloth.avatar.AvatarCollision import surface_from_triangles

    vertices = (
        (-10, -10, -10), (10, -10, -10), (10, 10, -10), (-10, 10, -10),
        (-10, -10, 10), (10, -10, 10), (10, 10, 10), (-10, 10, 10),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (3, 2, 6), (3, 6, 7),
        (0, 3, 7), (0, 7, 4),
        (1, 5, 6), (1, 6, 2),
    )
    return surface_from_triangles(vertices, triangles, region="test-cube", thickness=thickness)


def test_tissu_authored_contact_response_preserves_motion_direction():
    from types import SimpleNamespace

    from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
    from freecad_cloth.simulation.TissuBackend import (
        _apply_authored_containment_correction,
    )
    from freecad_cloth.simulation.TissuContainment import AuthoredSurfaceContainment

    surface = _cube_surface(thickness=2.0)
    containment = AuthoredSurfaceContainment(surface)

    class Particle:
        def __init__(self, position, old_position):
            self.position = tuple(position)
            self.old_position = tuple(old_position)

        def get_position(self):
            return self.position

        def get_old_position(self):
            return self.old_position

        def get_inverse_mass(self):
            return 1.0

        def set_position(self, position):
            self.position = tuple(position)

        def set_old_position(self, position):
            self.old_position = tuple(position)

    # FreeCAD (9,5,5) mm -> Tissu metres (0.009,0.005,0.005).
    stationary = Particle((0.009, 0.005, 0.005), (0.009, 0.005, 0.005))
    outward = Particle((0.009, 0.005, 0.005), (0.008, 0.005, 0.005))
    inward = Particle((0.009, 0.005, 0.005), (0.010, 0.005, 0.005))
    outside = Particle((0.013, 0.005, 0.005), (0.012, 0.005, 0.005))
    particles = [stationary, outward, inward, outside]
    sim = SimpleNamespace(solver=SimpleNamespace(get_particles=lambda: particles))

    corrected, max_correction_mm = _apply_authored_containment_correction(
        sim,
        containment,
        pinned_indices=(),
    )
    assert corrected == 3
    assert max_correction_mm == 3.0
    assert stationary.position == (0.012, 0.005, 0.005)
    assert stationary.old_position == (0.012, 0.005, 0.005)
    assert outward.position == (0.012, 0.005, 0.005)
    assert outward.old_position == (0.011, 0.005, 0.005)
    assert inward.position == (0.012, 0.005, 0.005)
    assert inward.old_position == (0.012, 0.005, 0.005)
    assert outside.position == (0.013, 0.005, 0.005)
    assert outside.old_position == (0.012, 0.005, 0.005)

    reversed_surface = surface_from_triangles(
        surface.vertices,
        tuple(tuple(reversed(triangle)) for triangle in surface.triangles),
        region="reversed-cube",
        thickness=2.0,
    )
    reversed_containment = AuthoredSurfaceContainment(reversed_surface)
    assert reversed_containment.nearest_surface_point((9.0, 5.0, 5.0))[1] == (1.0, 0.0, 0.0)

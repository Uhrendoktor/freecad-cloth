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


def _cube_surface(thickness=2.0, reverse=False):
    from freecad_cloth.avatar.AvatarCollision import surface_from_triangles

    vertices = (
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (10.0, 10.0, 10.0), (0.0, 10.0, 10.0),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    )
    if reverse:
        triangles = tuple((a, c, b) for a, b, c in triangles)
    return surface_from_triangles(vertices, triangles, region="cube", thickness=thickness)


def test_authored_containment_closed_mesh_orientation_and_correction():
    from freecad_cloth.simulation.TissuContainment import AuthoredSurfaceContainment

    for reverse in (False, True):
        containment = AuthoredSurfaceContainment(_cube_surface(thickness=2.0, reverse=reverse))
        assert containment.contains((5.0, 5.0, 5.0))
        assert not containment.contains((15.0, 5.0, 5.0))
        first = containment.nearest_surface_point((9.0, 5.0, 5.0))
        closest, normal, distance_sq, triangle_index = first
        assert closest == (10.0, 5.0, 5.0)
        assert normal == (1.0, 0.0, 0.0)
        assert distance_sq == 1.0
        assert triangle_index in {6, 7}
        assert containment.correct((9.0, 5.0, 5.0)) == (12.0, 5.0, 5.0)
        assert not containment.contains((12.0, 5.0, 5.0))


def test_authored_containment_normal_is_outward_for_reversed_winding():
    from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
    from freecad_cloth.simulation.TissuContainment import AuthoredSurfaceContainment

    surface = _cube_surface(thickness=2.0)
    reversed_surface = surface_from_triangles(
        surface.vertices,
        tuple(tuple(reversed(triangle)) for triangle in surface.triangles),
        region="reversed-cube",
        thickness=2.0,
    )
    containment = AuthoredSurfaceContainment(reversed_surface)
    assert containment.contains((5.0, 5.0, 5.0))
    closest, normal, distance_sq, triangle_index = containment.nearest_surface_point(
        (9.0, 5.0, 5.0)
    )
    assert closest == (10.0, 5.0, 5.0)
    assert normal == (1.0, 0.0, 0.0)
    assert distance_sq == 1.0
    assert triangle_index in {6, 7}
    assert containment.correct((9.0, 5.0, 5.0)) == (12.0, 5.0, 5.0)


def test_authored_containment_rejects_open_and_caches_authority():
    from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
    from freecad_cloth.simulation.TissuContainment import (
        AuthoredSurfaceContainment,
        get_authored_surface_containment,
    )

    open_surface = surface_from_triangles(
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        ((0, 1, 2),),
        region="open",
        thickness=1.0,
    )
    try:
        AuthoredSurfaceContainment(open_surface)
    except ValueError as exc:
        assert "must be closed" in str(exc)
    else:
        raise AssertionError("open authored surface was accepted")

    surface = _cube_surface()
    first = get_authored_surface_containment(surface)
    second = get_authored_surface_containment(surface)
    assert first is second
    assert first.surface is surface
    assert surface.thickness == 2.0


def test_authored_containment_is_explicitly_opt_in_and_resets_old_position():
    import os
    from types import SimpleNamespace

    from freecad_cloth.simulation.TissuBackend import (
        _apply_authored_containment_correction,
        _build_stitch_components,
        _tissu_authored_containment_enabled,
    )
    os.environ.pop("CLOTH_TISSU_AUTHORED_CONTAINMENT", None)
    assert not _tissu_authored_containment_enabled()
    os.environ["CLOTH_TISSU_AUTHORED_CONTAINMENT"] = "1"
    assert _tissu_authored_containment_enabled()

    class Particle:
        def __init__(self):
            self.position = (0.009, 0.005, 0.005)
            self.old_position = (0.010, 0.005, 0.005)

        def get_inverse_mass(self):
            return 1.0

        def get_position(self):
            return self.position

        def set_position(self, value):
            self.position = tuple(float(component) for component in value)

        def set_old_position(self, value):
            self.old_position = tuple(float(component) for component in value)

    particle = Particle()
    sim = SimpleNamespace(solver=SimpleNamespace(get_particles=lambda: [particle]))
    corrected, max_correction_mm = _apply_authored_containment_correction(
        sim,
        __import__("freecad_cloth.simulation.TissuContainment", fromlist=["AuthoredSurfaceContainment"]).AuthoredSurfaceContainment(_cube_surface()),
    )
    assert corrected == 1
    assert max_correction_mm == 3.0
    assert particle.position == (0.012, 0.005, 0.005)
    assert particle.old_position == (0.013, 0.005, 0.005)


if __name__ == "__main__":
    test_sphere_collision_pushes_particle_outside_surface()
    test_collision_and_structural_constraints_can_coexist()
    test_authored_containment_closed_mesh_orientation_and_correction()
    test_authored_containment_normal_is_outward_for_reversed_winding()
    test_authored_containment_rejects_open_and_caches_authority()
    test_authored_containment_is_explicitly_opt_in_and_resets_old_position()
    print("collision tests passed")


def test_authored_containment_rigidly_translates_stitch_components():
    from types import SimpleNamespace
    from freecad_cloth.simulation.TissuContainment import AuthoredSurfaceContainment

    class Particle:
        def __init__(self, x):
            self.position = (x, 0.005, 0.005)
            self.old_position = (x + 0.001, 0.005, 0.005)

        def get_inverse_mass(self):
            return 1.0

        def get_position(self):
            return self.position

        def get_old_position(self):
            return self.old_position

        def set_position(self, value):
            self.position = tuple(float(component) for component in value)

        def set_old_position(self, value):
            self.old_position = tuple(float(component) for component in value)

    particles = [Particle(0.009), Particle(0.0085)]
    sim = SimpleNamespace(solver=SimpleNamespace(get_particles=lambda: particles))
    component = _build_stitch_components(((0, 1),), len(particles))
    corrected, _max_correction_mm = _apply_authored_containment_correction(
        sim,
        AuthoredSurfaceContainment(_cube_surface()),
        stitch_components=component,
        stitch_edges=((0, 1),),
    )

    assert corrected == 2
    assert particles[0].position[0] > 0.011
    assert particles[1].position[0] > 0.011
    assert abs(particles[0].position[0] - particles[1].position[0] - 0.0005) < 1e-12
    assert abs(
        (particles[0].position[0] - particles[0].old_position[0]) + 0.001
    ) < 1e-12
    assert abs(
        (particles[1].position[0] - particles[1].old_position[0]) + 0.001
    ) < 1e-12

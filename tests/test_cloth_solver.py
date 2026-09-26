import os
from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle


def test_deterministic_step_and_pins():
    a = ClothSystem.grid(40, 20, nx=4, ny=3, origin=(0, 0, 50))
    b = ClothSystem.grid(40, 20, nx=4, ny=3, origin=(0, 0, 50))
    for system in (a, b):
        system.pin((0, 3))
        system.step(dt=1/60, iterations=6)
        assert system.finite()
    assert [p.position() for p in a.particles] == [p.position() for p in b.particles]
    assert a.particles[0].position() == (0, 0, 50)
    assert a.particles[-1].z < 50


def test_first_step_has_no_artificial_velocity():
    particle = Particle(120.0, -35.0, 800.0)
    system = ClothSystem([particle])
    system.step(dt=1/60, iterations=1, gravity=(0.0, 0.0, 0.0))
    assert particle.position() == (120.0, -35.0, 800.0)


def test_sewing_reduces_gap():
    system = ClothSystem.grid(20, 10, nx=3, ny=3, origin=(0, 0, 30))
    offset = len(system.particles)
    other = ClothSystem.grid(20, 10, nx=3, ny=3, origin=(30, 0, 30))
    system.particles.extend(other.particles)
    system.constraints.extend(type(c)(c.a+offset, c.b+offset, c.rest, c.compliance) for c in other.constraints)
    pairs = [(2, offset), (5, offset+3), (8, offset+6)]
    system.add_stitches(pairs)
    before = abs(system.particles[2].x - system.particles[offset].x)
    system.step(dt=1/60, iterations=10, gravity=(0, 0, 0))
    after = abs(system.particles[2].x - system.particles[offset].x)
    assert after < before


def _cube_collision_surface(thickness=1.0):
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
    return surface_from_triangles(vertices, triangles, thickness=thickness)


def test_mesh_collision_corner_projects_against_both_local_faces():
    surface = _cube_collision_surface()
    particle = Particle(10.5, 10.5, 0.0)
    system = ClothSystem([particle])

    system._collide_surface(surface)

    assert particle.position() == (11.0, 11.0, 0.0)


def test_tissu_signed_collision_guard_math_and_env_gate():
    from freecad_cloth.simulation.TissuBackend import _signed_collision_guard_correction, _tissu_signed_collision_guard
    import numpy as np

    original = os.environ.pop("CLOTH_TISSU_SIGNED_COLLISION_GUARD", None)
    try:
        assert _tissu_signed_collision_guard() is False
        os.environ["CLOTH_TISSU_SIGNED_COLLISION_GUARD"] = "1"
        assert _tissu_signed_collision_guard() is True
        os.environ["CLOTH_TISSU_SIGNED_COLLISION_GUARD"] = "false"
        assert _tissu_signed_collision_guard() is False

        position = np.asarray((0.02, 0.0, -0.01), dtype=np.float64)
        old_position = np.asarray((0.01, 0.0, 0.0), dtype=np.float64)
        closest = np.asarray((0.02, 0.0, 0.0), dtype=np.float64)
        normal = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        correction = _signed_collision_guard_correction(position, old_position, closest, normal, 0.002)
        assert correction is not None
        corrected, corrected_old, penetration = correction
        assert tuple(corrected) == (0.02, 0.0, 0.002)
        assert tuple(corrected - corrected_old) == (0.01, 0.0, 0.0)
        assert abs(penetration - 0.01) <= 1e-12
        outside = np.asarray((0.02, 0.0, 0.01), dtype=np.float64)
        assert _signed_collision_guard_correction(outside, old_position, closest, normal, 0.002) is None
    finally:
        if original is None:
            os.environ.pop("CLOTH_TISSU_SIGNED_COLLISION_GUARD", None)
        else:
            os.environ["CLOTH_TISSU_SIGNED_COLLISION_GUARD"] = original


def test_tissu_signed_collision_bvh_preserves_authored_outward_winding():
    from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
    from freecad_cloth.simulation.TissuBackend import _build_signed_collision_bvh, _nearest_signed_collision, _to_tissu_position, _signed_collision_guard_correction
    import numpy as np

    vertices = (
        (-10, -10, -10), (10, -10, -10), (10, 10, -10), (-10, 10, -10),
        (-10, -10, 10), (10, -10, 10), (10, 10, 10), (-10, 10, 10),
    )
    outward = (
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (3, 6, 2), (3, 7, 6),
        (0, 4, 7), (0, 7, 3),
        (1, 2, 6), (1, 6, 5),
    )
    surface = surface_from_triangles(vertices, outward, thickness=1.0)
    bvh = _build_signed_collision_bvh(surface)
    point = np.asarray(_to_tissu_position((0.0, 0.0, 0.0)), dtype=np.float64)
    nearest = _nearest_signed_collision(bvh, point)
    assert nearest is not None
    closest, normal, distance = nearest
    assert distance > 0.0
    assert float(np.dot(point - closest, normal)) < 0.0
    correction = _signed_collision_guard_correction(
        point,
        np.asarray(_to_tissu_position((0.0, 0.0, 0.0)), dtype=np.float64),
        closest,
        normal,
        0.002,
    )
    assert correction is not None



def test_tissu_collision_surface_abi_preserves_solver_surface_identity():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    backend_source = (root / "freecad_cloth" / "simulation" / "ClothBackend.py").read_text(encoding="utf-8")
    tissu_source = (root / "freecad_cloth" / "simulation" / "TissuBackend.py").read_text(encoding="utf-8")
    objects_source = (root / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")

    assert "def solver_collision_surface(self):" in backend_source
    assert "def solver_collision_surface(self):" in tissu_source
    assert "return self._collision_surface" in tissu_source
    assert "self.backend.solver_collision_surface" in objects_source
    assert "else collision_surface" in objects_source


def test_mesh_collision_edge_projection_is_idempotent():
    surface = _cube_collision_surface()
    particle = Particle(10.5, 0.0, 10.5)
    system = ClothSystem([particle])

    system._collide_surface(surface)
    projected = particle.position()
    system._collide_surface(surface)

    assert projected == (11.0, 0.0, 11.0)
    drift = tuple(a - b for a, b in zip(particle.position(), projected))
    assert max(abs(value) for value in drift) <= 1e-9, drift


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            test()
    print("cloth solver tests passed")

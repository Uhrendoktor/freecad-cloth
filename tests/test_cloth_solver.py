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


def test_tissu_collision_surface_abi_preserves_solver_surface_identity():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    backend_source = (root / "freecad_cloth" / "simulation" / "ClothBackend.py").read_text(encoding="utf-8")
    tissu_source = (root / "freecad_cloth" / "simulation" / "TissuBackend.py").read_text(encoding="utf-8")
    objects_source = (root / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")

    assert "def solver_collision_surface(self):" in backend_source
    assert "def solver_collision_surface(self):" in tissu_source
    assert "return self._collision_surface" in tissu_source
    assert "self.collision_surface = collision_surface" in objects_source
    assert "_collision_surface_for_step(self)" in objects_source


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



def test_tissu_particle_binding_mutates_solver_state_when_available():
    import importlib.util
    if importlib.util.find_spec("tissu") is None:
        return
    import numpy as np
    from tissu import Simulation

    sim = Simulation(substeps=1, iterations=1, gravity=0.0, thickness=0.002)
    sim.create_from_arrays(
        "probe",
        np.asarray([[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [0.0, 0.01, 0.0]], dtype=np.float64),
        np.asarray([[0, 1, 2]], dtype=np.int32),
    )
    before = tuple(float(v) for v in sim.positions[0])
    particle = sim.solver.get_particles()[0]
    target = np.asarray([0.123, 0.0, 0.0], dtype=np.float64)
    particle.set_position(target)
    particle.set_old_position(target)
    after = tuple(float(v) for v in sim.positions[0])
    assert before != after, (before, after)
    assert after[0] == 0.123, (before, after)


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            test()
    print("cloth solver tests passed")

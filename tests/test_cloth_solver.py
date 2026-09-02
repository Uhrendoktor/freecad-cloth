from freecad_cloth.simulation.ClothSolver import ClothSystem


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

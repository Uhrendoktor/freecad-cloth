from freecad_cloth.simulation.ClothSolver import ClothSystem, DistanceConstraint, Particle


def test_grid_builds_deterministic_solver_input():
    a = ClothSystem.grid(40, 20, nx=4, ny=3, origin=(0, 0, 50))
    b = ClothSystem.grid(40, 20, nx=4, ny=3, origin=(0, 0, 50))

    assert [particle.position() for particle in a.particles] == [
        particle.position() for particle in b.particles
    ]
    assert len(a.particles) == 12
    assert len(a.constraints) == len(b.constraints)


def test_solver_input_records_stitches_once():
    system = ClothSystem(
        [Particle(0.0, 0.0, 0.0), Particle(10.0, 0.0, 0.0)],
        stitches=[(0, 1)],
    )

    assert system.stitches == [
        DistanceConstraint(0, 1, 0.0, 0.0),
    ]


def test_pins_zero_inverse_mass_without_integrating_physics():
    system = ClothSystem([Particle(0.0, 0.0, 50.0), Particle(1.0, 0.0, 50.0)])
    system.pin((0,))

    assert system.pins == {0: (0.0, 0.0, 50.0)}
    assert system.particles[0].inv_mass == 0.0
    assert system.particles[1].inv_mass == 1.0


def test_solver_input_rejects_invalid_indices():
    system = ClothSystem([Particle(0.0, 0.0, 0.0)])

    try:
        system.pin((1,))
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-range pin must fail")

    try:
        system.add_stitches(((0, 1),))
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-range stitch must fail")


def test_finite_checks_only_input_coordinates():
    system = ClothSystem([Particle(0.0, 0.0, 0.0)])
    assert system.finite()

    system.particles[0].z = float("nan")
    assert not system.finite()

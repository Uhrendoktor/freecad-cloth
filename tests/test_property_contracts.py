"""Property and stateful tests for deterministic core models."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle, distance


@given(
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
)
def test_particle_distance_is_symmetric(x: float, y: float, z: float) -> None:
    """Euclidean distance is symmetric and zero for identical inputs."""
    a = Particle(x, y, z)
    b = Particle(-x, y, -z)
    assert distance(a, b) == distance(b, a)
    assert distance(a, a) == 0.0


class ClothSystemStateMachine(RuleBasedStateMachine):
    """Exercise sequences of solver-input mutations while preserving invariants."""

    def __init__(self) -> None:
        super().__init__()
        self.system = ClothSystem.grid(10.0, 10.0, nx=3, ny=3)

    @rule(index=st.integers(min_value=0, max_value=8))
    def pin_particle(self, index: int) -> None:
        """Pin a valid particle index."""
        self.system.pin([index])

    @rule(
        a=st.integers(min_value=0, max_value=8),
        b=st.integers(min_value=0, max_value=8),
    )
    def add_stitch(self, a: int, b: int) -> None:
        """Add a valid sewing-input pair."""
        self.system.add_stitches([(a, b)])

    @invariant()
    def input_state_remains_finite(self) -> None:
        """Every generated state remains numerically finite."""
        assert self.system.finite()

    @invariant()
    def pinned_particles_have_zero_inverse_mass(self) -> None:
        """Every recorded pin remains represented by zero inverse mass."""
        for index in self.system.pins:
            assert self.system.particles[index].inv_mass == 0.0


def test_cloth_system_state_machine() -> None:
    """Run bounded stateful exploration of the solver-input model."""
    run_state_machine_as_test(
        ClothSystemStateMachine,
        settings=settings(max_examples=20, stateful_step_count=12),
    )

"""Property and stateful tests for deterministic core models."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from freecad_cloth.pattern.PatternSchema import PatternDocument, dumps, loads
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


@given(
    piece_id=st.text(min_size=1, max_size=24),
    name=st.text(min_size=1, max_size=24),
    metadata_value=st.recursive(
        st.none()
        | st.booleans()
        | st.integers()
        | st.floats(allow_nan=False, allow_infinity=False)
        | st.text(),
        lambda children: st.lists(children, max_size=3)
        | st.dictionaries(st.text(max_size=8), children, max_size=3),
        max_leaves=12,
    ),
)
def test_pattern_document_round_trip(piece_id: str, name: str, metadata_value: object) -> None:
    """Canonical serialization round-trips a valid document exactly."""
    document = PatternDocument(
        pattern_id="property-test",
        name=name,
        pieces=[{"id": piece_id}],
        metadata={"value": metadata_value},
    )
    assert loads(dumps(document)) == document


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

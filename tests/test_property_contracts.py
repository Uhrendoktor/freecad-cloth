"""Property and stateful tests for deterministic core models."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from freecad_cloth.sewing.SewingCorrespondence import arc_length_vertex_indices, map_parameter
from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle, distance


@given(
    st.floats(min_value=-1e100, max_value=1e100, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-1e100, max_value=1e100, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-1e100, max_value=1e100, allow_nan=False, allow_infinity=False),
)
def test_particle_distance_is_symmetric(x: float, y: float, z: float) -> None:
    """Euclidean distance is symmetric and zero for identical inputs."""
    a = Particle(x, y, z)
    b = Particle(-x, y, -z)
    assert distance(a, b) == distance(b, a)
    assert distance(a, a) == 0.0


def test_particle_distance_rejects_unrepresentable_finite_coordinates() -> None:
    """Finite coordinates can have a Euclidean distance outside float range."""
    with pytest.raises(ValueError, match="distance must be finite"):
        distance(Particle(0.0, 0.0, 1e308), Particle(0.0, 0.0, -1e308))


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


def test_solver_distance_avoids_intermediate_square_overflow() -> None:
    """The standard-library Euclidean distance remains stable for large finite coordinates."""
    large = 1e200
    assert distance(Particle(large, 0.0, 0.0), Particle(0.0, 0.0, 0.0)) == large


@given(
    parameter_a=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    parameter_b=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    start_a=st.floats(
        min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False
    ),
    span_a=st.floats(
        min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    start_b=st.floats(
        min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False
    ),
    span_b=st.floats(
        min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    reversed_b=st.booleans(),
)
def test_seam_parameter_mapping_preserves_bounds_and_direction(
    parameter_a: float,
    parameter_b: float,
    start_a: float,
    span_a: float,
    start_b: float,
    span_b: float,
    reversed_b: bool,
) -> None:
    """Mapping stays within B's range and respects optional orientation reversal."""
    end_a = min(1.0, start_a + span_a)
    end_b = min(1.0, start_b + span_b)
    mapped_a = map_parameter(parameter_a, start_a, end_a, start_b, end_b, reversed_b)
    mapped_b = map_parameter(parameter_b, start_a, end_a, start_b, end_b, reversed_b)

    assert start_b <= mapped_a <= end_b
    assert start_b <= mapped_b <= end_b
    if parameter_a <= parameter_b:
        assert mapped_a <= mapped_b if not reversed_b else mapped_a >= mapped_b
    else:
        assert mapped_a >= mapped_b if not reversed_b else mapped_a <= mapped_b


@given(
    segment_lengths=st.lists(
        st.floats(
            min_value=0.01,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=16,
    ),
    requested_count=st.integers(min_value=2, max_value=24),
)
def test_arc_length_sampling_preserves_distinct_monotone_topology(
    segment_lengths: list[float], requested_count: int
) -> None:
    """Arc-length correspondence never repeats, invents, or reorders vertices."""
    coordinates = [0.0]
    for segment_length in segment_lengths:
        coordinates.append(coordinates[-1] + segment_length)
    points = tuple((coordinate, 0.0) for coordinate in coordinates)
    vertex_ids = tuple(range(len(points)))

    selected = arc_length_vertex_indices(vertex_ids, points, requested_count)

    assert len(selected) == min(requested_count, len(vertex_ids))
    assert selected[0] == vertex_ids[0]
    assert selected[-1] == vertex_ids[-1]
    assert all(left < right for left, right in zip(selected, selected[1:], strict=False))


def test_seam_parameter_mapping_rejects_invalid_intervals() -> None:
    """A reversed range is rejected rather than repaired silently."""
    with pytest.raises(ValueError, match="parameter ranges"):
        map_parameter(0.5, start_a=0.8, end_a=0.2)


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False, width=32),
            st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False, width=32),
            st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False, width=32),
        ),
        min_size=3,
        max_size=8,
        unique=True,
    ),
    st.tuples(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False, width=32),
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False, width=32),
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False, width=32),
    ),
)
@settings(max_examples=80, deadline=None)
def test_semantic_attachment_vertex_selection_is_order_independent(
    positions: list[tuple[float, float, float]], anchor: tuple[float, float, float]
) -> None:
    """The nearest allowed semantic-edge vertex is independent of boundary ordering."""
    from hypothesis import assume
    from math import sqrt
    from freecad_cloth.simulation.ClothAttachments import select_attachment_particle_near_anchor

    distances = [
        sqrt(sum((positions[index][axis] - anchor[axis]) ** 2 for axis in range(3)))
        for index in range(len(positions))
    ]
    order = sorted(range(len(distances)), key=lambda index: (distances[index], index))
    assume(distances[order[1]] - distances[order[0]] > 1e-3)
    expected = order[0]
    forward = select_attachment_particle_near_anchor(tuple(range(len(positions))), positions, anchor)
    reverse = select_attachment_particle_near_anchor(tuple(reversed(range(len(positions)))), positions, anchor)
    assert forward == expected
    assert reverse == expected


def test_solver_distance_avoids_intermediate_square_overflow() -> None:
    """The standard-library Euclidean distance remains stable for large finite coordinates."""
    large = 1e200
    assert distance(Particle(large, 0.0, 0.0), Particle(0.0, 0.0, 0.0)) == large


@given(
    parameter_a=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    parameter_b=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    start_a=st.floats(
        min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False
    ),
    span_a=st.floats(
        min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    start_b=st.floats(
        min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False
    ),
    span_b=st.floats(
        min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    reversed_b=st.booleans(),
)
def test_seam_parameter_mapping_preserves_bounds_and_direction(
    parameter_a: float,
    parameter_b: float,
    start_a: float,
    span_a: float,
    start_b: float,
    span_b: float,
    reversed_b: bool,
) -> None:
    """Mapping stays within B's range and respects optional orientation reversal."""
    end_a = min(1.0, start_a + span_a)
    end_b = min(1.0, start_b + span_b)
    mapped_a = map_parameter(parameter_a, start_a, end_a, start_b, end_b, reversed_b)
    mapped_b = map_parameter(parameter_b, start_a, end_a, start_b, end_b, reversed_b)

    assert start_b <= mapped_a <= end_b
    assert start_b <= mapped_b <= end_b
    if parameter_a <= parameter_b:
        assert mapped_a <= mapped_b if not reversed_b else mapped_a >= mapped_b
    else:
        assert mapped_a >= mapped_b if not reversed_b else mapped_a <= mapped_b


@given(
    segment_lengths=st.lists(
        st.floats(
            min_value=0.01,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=16,
    ),
    requested_count=st.integers(min_value=2, max_value=24),
)
def test_arc_length_sampling_preserves_distinct_monotone_topology(
    segment_lengths: list[float], requested_count: int
) -> None:
    """Arc-length correspondence never repeats, invents, or reorders vertices."""
    coordinates = [0.0]
    for segment_length in segment_lengths:
        coordinates.append(coordinates[-1] + segment_length)
    points = tuple((coordinate, 0.0) for coordinate in coordinates)
    vertex_ids = tuple(range(len(points)))

    selected = arc_length_vertex_indices(vertex_ids, points, requested_count)

    assert len(selected) == min(requested_count, len(vertex_ids))
    assert selected[0] == vertex_ids[0]
    assert selected[-1] == vertex_ids[-1]
    assert all(left < right for left, right in zip(selected, selected[1:], strict=False))


def test_seam_parameter_mapping_rejects_invalid_intervals() -> None:
    """A reversed range is rejected rather than repaired silently."""
    with pytest.raises(ValueError, match="parameter ranges"):
        map_parameter(0.5, start_a=0.8, end_a=0.2)

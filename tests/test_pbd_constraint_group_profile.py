# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for read-only profiling of native pyPBD constraint groups."""

from __future__ import annotations

from typing import cast

import pytest

from tools.ci.pbd_constraint_group_profile import (
    DEFAULT_OPENMP_PARALLEL_THRESHOLD,
    ConstraintGroupModel,
    profile_native_constraint_groups,
    summarize_constraint_groups,
)


class _FakeConstraintModel:
    """Small structural fake for the pyPBD constraint-group bindings."""

    def __init__(self, groups: list[list[int]]) -> None:
        """Store a native-like grouping and a matching constraint collection."""
        self._groups = groups
        self._constraints = list(range(sum(len(group) for group in groups)))

    def getConstraintGroups(self) -> list[list[int]]:
        """Return the fake native constraint groups."""
        return self._groups

    def getConstraints(self) -> list[int]:
        """Return the fake native constraint collection."""
        return self._constraints


def test_group_profile_reports_histogram_and_openmp_eligible_work() -> None:
    """Groups at the exact OpenMP threshold remain sequential."""
    sizes = [1, 16, 17, 32, 33, 64, 65, 127, 128, 255, 256]
    groups: list[list[int]] = []
    next_index = 0
    for size in sizes:
        groups.append(list(range(next_index, next_index + size)))
        next_index += size

    profile = summarize_constraint_groups(groups, next_index)

    assert profile["constraint_count"] == next_index
    assert profile["group_count"] == len(sizes)
    assert profile["min_group_size"] == 1
    assert profile["max_group_size"] == 256
    assert profile["mean_group_size"] == pytest.approx(sum(sizes) / len(sizes))
    assert profile["median_group_size"] == 64.0
    assert profile["p90_group_size"] == 255
    assert profile["p95_group_size"] == 256
    assert profile["openmp_parallel_threshold"] == DEFAULT_OPENMP_PARALLEL_THRESHOLD
    assert profile["parallel_eligible_group_count"] == 5
    assert profile["parallel_eligible_constraint_count"] == 831
    assert profile["sequential_group_count"] == 6
    assert profile["group_size_histogram"] == {
        "1-16": 2,
        "17-32": 2,
        "33-64": 2,
        "65-127": 2,
        "128-255": 2,
        "256+": 1,
    }


def test_group_profile_nearest_rank_percentiles_handle_exact_boundaries() -> None:
    """Percentile ranks stay exact when the scaled percentile is an integer."""
    for group_count, expected_p90, expected_p95 in (
        (10, 9, 10),
        (20, 18, 19),
    ):
        groups: list[list[int]] = []
        next_index = 0
        for size in range(1, group_count + 1):
            groups.append(list(range(next_index, next_index + size)))
            next_index += size

        profile = summarize_constraint_groups(groups, next_index)

        assert profile["p90_group_size"] == expected_p90
        assert profile["p95_group_size"] == expected_p95


def test_native_profile_reads_existing_grouping_without_mutating_it() -> None:
    """The native adapter only reads the groups already produced by pyPBD."""
    groups = [[0, 1, 2], [3, 4], [5]]
    model = _FakeConstraintModel(groups)
    original = [list(group) for group in groups]

    profile = profile_native_constraint_groups(cast(ConstraintGroupModel, model))

    assert profile["constraint_count"] == 6
    assert profile["group_count"] == 3
    assert model.getConstraintGroups() == original


@pytest.mark.parametrize(
    ("groups", "constraint_count", "message"),
    [
        ([], 1, "empty"),
        ([[0], []], 1, "empty"),
        ([[0, 0]], 2, "duplicate"),
        ([[0]], 2, "for 2 constraints"),
        ([[0, 2]], 2, "out of range"),
    ],
)
def test_group_profile_rejects_invalid_native_partitions(
    groups: list[list[int]],
    constraint_count: int,
    message: str,
) -> None:
    """Reject stale, incomplete, duplicate, or invalid native group indices."""
    with pytest.raises(ValueError, match=message):
        summarize_constraint_groups(groups, constraint_count)


@pytest.mark.parametrize("threshold", [-1, True, 1.5])
def test_group_profile_rejects_invalid_openmp_threshold(threshold: int | float | bool) -> None:
    """Threshold metadata must be a non-negative integer."""
    with pytest.raises(ValueError, match="parallel_threshold"):
        summarize_constraint_groups([[0]], 1, parallel_threshold=cast(int, threshold))

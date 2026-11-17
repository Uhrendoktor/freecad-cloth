# Copyright (C) 2026 FreeCAD Cloth contributors
"""Summarize native pyPBD constraint-group sizes without changing solver state."""

import math
from collections.abc import Sequence, Sized
from typing import Protocol, TypedDict


DEFAULT_OPENMP_PARALLEL_THRESHOLD = 64


class ConstraintGroupModel(Protocol):
    """Native model methods needed for read-only constraint-group profiling."""

    def getConstraintGroups(self) -> Sequence[Sequence[int]]:
        """Return the native solver's conflict-free constraint groups."""
        ...

    def getConstraints(self) -> Sized:
        """Return the native solver's complete constraint collection."""
        ...


class ConstraintGroupProfile(TypedDict):
    """JSON-safe distribution summary for one initialized native model."""

    schema_version: int
    source: str
    constraint_count: int
    group_count: int
    min_group_size: int
    max_group_size: int
    mean_group_size: float
    median_group_size: float
    p90_group_size: int
    p95_group_size: int
    openmp_parallel_threshold: int
    parallel_eligible_group_count: int
    parallel_eligible_group_fraction: float
    parallel_eligible_constraint_count: int
    parallel_eligible_constraint_fraction: float
    sequential_group_count: int
    group_size_histogram: dict[str, int]


def _nearest_rank(ordered_values: Sequence[int], percentile: float) -> int:
    """Return the nearest-rank percentile from an ascending non-empty sequence."""
    nearest_rank = math.ceil(percentile * len(ordered_values))
    index = max(0, min(len(ordered_values) - 1, nearest_rank - 1))
    return ordered_values[index]


def summarize_constraint_groups(
    groups: Sequence[Sequence[int]],
    constraint_count: int,
    *,
    parallel_threshold: int = DEFAULT_OPENMP_PARALLEL_THRESHOLD,
) -> ConstraintGroupProfile:
    """Summarize group sizes and verify they partition the native constraints exactly.

    pyPBD's position projection uses an OpenMP parallel region when a group has
    strictly more members than MIN_PARALLEL_SIZE. This function records the
    existing grouping and threshold only; it does not call initialization,
    reorder groups, or change parallel execution.

    Args:
        groups: Native constraint groups, each containing native constraint indices.
        constraint_count: Total number of native constraints in the model.
        parallel_threshold: Upstream OpenMP threshold (parallel execution is used for
            group sizes strictly greater than this value).

    Returns:
        A JSON-safe distribution summary including histogram and parallel eligibility.

    Raises:
        ValueError: If groups do not partition all native constraint indices exactly once.
    """
    if isinstance(constraint_count, bool) or not isinstance(constraint_count, int):
        raise ValueError("constraint_count must be an integer")
    if constraint_count <= 0:
        raise ValueError("constraint_count must be positive")
    if isinstance(parallel_threshold, bool) or not isinstance(parallel_threshold, int):
        raise ValueError("parallel_threshold must be an integer")
    if parallel_threshold < 0:
        raise ValueError("parallel_threshold must be non-negative")
    if not groups:
        raise ValueError("native constraint groups are empty")

    group_sizes: list[int] = []
    constraint_indices: list[int] = []
    for group_index, group in enumerate(groups):
        if not group:
            raise ValueError(f"native constraint group {group_index} is empty")
        for raw_index in group:
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise ValueError("native constraint indices must be integers")
            if raw_index < 0 or raw_index >= constraint_count:
                raise ValueError(f"native constraint index {raw_index} is out of range")
            constraint_indices.append(raw_index)
        group_sizes.append(len(group))

    if len(constraint_indices) != constraint_count:
        raise ValueError(
            "native constraint groups contain "
            f"{len(constraint_indices)} indices for {constraint_count} constraints"
        )
    if len(set(constraint_indices)) != constraint_count:
        raise ValueError("native constraint groups contain duplicate constraint indices")

    ordered_sizes = sorted(group_sizes)
    parallel_group_sizes = [size for size in group_sizes if size > parallel_threshold]
    parallel_constraint_count = sum(parallel_group_sizes)
    group_count = len(group_sizes)
    histogram = {
        "1-16": sum(1 <= size <= 16 for size in group_sizes),
        "17-32": sum(17 <= size <= 32 for size in group_sizes),
        "33-64": sum(33 <= size <= 64 for size in group_sizes),
        "65-127": sum(65 <= size <= 127 for size in group_sizes),
        "128-255": sum(128 <= size <= 255 for size in group_sizes),
        "256+": sum(size >= 256 for size in group_sizes),
    }
    midpoint = group_count // 2
    if group_count % 2:
        median_size = float(ordered_sizes[midpoint])
    else:
        median_size = 0.5 * (ordered_sizes[midpoint - 1] + ordered_sizes[midpoint])

    return {
        "schema_version": 1,
        "source": "pyPBD.SimulationModel.getConstraintGroups",
        "constraint_count": constraint_count,
        "group_count": group_count,
        "min_group_size": ordered_sizes[0],
        "max_group_size": ordered_sizes[-1],
        "mean_group_size": sum(group_sizes) / group_count,
        "median_group_size": median_size,
        "p90_group_size": _nearest_rank(ordered_sizes, 0.90),
        "p95_group_size": _nearest_rank(ordered_sizes, 0.95),
        "openmp_parallel_threshold": parallel_threshold,
        "parallel_eligible_group_count": len(parallel_group_sizes),
        "parallel_eligible_group_fraction": len(parallel_group_sizes) / group_count,
        "parallel_eligible_constraint_count": parallel_constraint_count,
        "parallel_eligible_constraint_fraction": parallel_constraint_count / constraint_count,
        "sequential_group_count": group_count - len(parallel_group_sizes),
        "group_size_histogram": histogram,
    }


def profile_native_constraint_groups(model: ConstraintGroupModel) -> ConstraintGroupProfile:
    """Read and summarize the already-initialized native model's constraint groups."""
    return summarize_constraint_groups(model.getConstraintGroups(), len(model.getConstraints()))

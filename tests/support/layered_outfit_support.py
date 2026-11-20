# Copyright (C) 2026 FreeCAD Cloth contributors
"""Collision-aware support selection for layered-outfit acceptance fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite


def select_top_boundary_supports(
    top_chains: Mapping[str, Sequence[int]],
    exterior_by_particle: Mapping[int, bool],
    clearance_by_particle: Mapping[int, float],
    *,
    minimum_clearance_mm: float,
    samples_per_chain: int = 3,
) -> dict[str, tuple[int, ...]]:
    """Select evenly distributed top-edge supports with safe body clearance.

    Args:
        top_chains: Authored top-boundary particle indices in panel-edge order.
        exterior_by_particle: Closed-mesh classification for each candidate.
        clearance_by_particle: Exact nearest-surface distance for each candidate.
        minimum_clearance_mm: Required unsigned distance from the mannequin.
        samples_per_chain: Number of distributed anchors required per panel.

    Returns:
        One ordered tuple of safe support indices for each authored panel edge.

    Raises:
        ValueError: If an edge cannot provide enough unique exterior supports.
    """
    minimum_clearance = float(minimum_clearance_mm)
    if not isfinite(minimum_clearance) or minimum_clearance < 0.0:
        raise ValueError("minimum support clearance must be finite and non-negative")
    if (
        isinstance(samples_per_chain, bool)
        or not isinstance(samples_per_chain, int)
        or samples_per_chain < 1
    ):
        raise ValueError("support sample count must be a positive integer")

    selections: dict[str, tuple[int, ...]] = {}
    used_indices: set[int] = set()
    for panel_name, authored_chain in top_chains.items():
        chain = tuple(authored_chain)
        if len(chain) != len(set(chain)) or any(
            isinstance(index, bool) or not isinstance(index, int) or index < 0
            for index in chain
        ):
            raise ValueError(
                "top boundary contains invalid or duplicate particle indices: " + panel_name
            )

        eligible: list[int] = []
        for index in chain:
            if exterior_by_particle.get(index) is not True:
                continue
            try:
                clearance = float(clearance_by_particle[index])
            except (KeyError, TypeError, ValueError):
                continue
            if isfinite(clearance) and clearance >= minimum_clearance:
                eligible.append(index)

        if len(eligible) < samples_per_chain:
            particle_label = "particle" if len(eligible) == 1 else "particles"
            raise ValueError(
                "top boundary %s has only %d exterior %s with %.3f mm clearance; requires %d"
                % (
                    panel_name,
                    len(eligible),
                    particle_label,
                    minimum_clearance,
                    samples_per_chain,
                )
            )

        if samples_per_chain == 1:
            selected = (eligible[len(eligible) // 2],)
        else:
            selected = tuple(
                eligible[round(sample * (len(eligible) - 1) / (samples_per_chain - 1))]
                for sample in range(samples_per_chain)
            )
        if len(selected) != samples_per_chain:
            raise ValueError("top boundary support selection is not unique: " + panel_name)
        reused = used_indices.intersection(selected)
        if reused:
            raise ValueError(
                "shirt support particle is reused by multiple panel boundaries: "
                + panel_name
                + " "
                + repr(sorted(reused))
            )
        used_indices.update(selected)
        selections[str(panel_name)] = selected

    return selections

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
            isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in chain
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


def select_landmark_supports(
    candidate_chains: Mapping[str, Sequence[int]],
    targets_by_chain: Mapping[str, Sequence[float]],
    positions: Sequence[Sequence[float]],
    exterior_by_particle: Mapping[int, bool],
    clearance_by_particle: Mapping[int, float],
    *,
    minimum_clearance_mm: float,
    maximum_clearance_mm: float,
) -> dict[str, int]:
    """Select one nearby exterior particle for each anatomical support target.

    Unlike a distributed top-rim pin set, this selector keeps supports local to
    named body landmarks and rejects particles that are too far from the target
    surface to represent a credible garment support.

    Args:
        candidate_chains: Authored boundary particle indices, keyed by panel.
        targets_by_chain: Desired world-space support position for each panel.
        positions: Current world-space solver particle positions in millimetres.
        exterior_by_particle: Closed-mesh classification for candidate particles.
        clearance_by_particle: Nearest mannequin-surface distance per candidate.
        minimum_clearance_mm: Minimum allowed separation from the mannequin.
        maximum_clearance_mm: Maximum allowed separation from the mannequin.

    Returns:
        One unique solver particle index for each requested panel support.

    Raises:
        ValueError: If a target, candidate chain, or safe support particle is invalid.
    """
    minimum_clearance = float(minimum_clearance_mm)
    maximum_clearance = float(maximum_clearance_mm)
    if (
        not isfinite(minimum_clearance)
        or not isfinite(maximum_clearance)
        or minimum_clearance < 0.0
        or maximum_clearance < minimum_clearance
    ):
        raise ValueError("support clearance limits must be finite and ordered")

    if set(candidate_chains) != set(targets_by_chain):
        raise ValueError("each support boundary must have exactly one named target")

    selections: dict[str, int] = {}
    used_indices: set[int] = set()
    for panel_name, authored_chain in candidate_chains.items():
        chain = tuple(authored_chain)
        if not chain or len(chain) != len(set(chain)):
            raise ValueError(
                "support boundary is empty or contains duplicate particles: " + panel_name
            )
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= len(positions)
            for index in chain
        ):
            raise ValueError("support boundary contains an invalid particle index: " + panel_name)

        target = tuple(float(value) for value in targets_by_chain[panel_name])
        if len(target) != 3 or not all(isfinite(value) for value in target):
            raise ValueError(
                "support target must contain three finite world coordinates: " + panel_name
            )

        eligible: list[int] = []
        for index in chain:
            if exterior_by_particle.get(index) is not True:
                continue
            try:
                clearance = float(clearance_by_particle[index])
            except (KeyError, TypeError, ValueError):
                continue
            if isfinite(clearance) and minimum_clearance <= clearance <= maximum_clearance:
                eligible.append(index)

        if not eligible:
            raise ValueError(
                "support boundary %s has no exterior particle within %.3f..%.3f mm clearance"
                % (panel_name, minimum_clearance, maximum_clearance)
            )

        selected = min(
            eligible,
            key=lambda index: (
                sum((float(positions[index][axis]) - target[axis]) ** 2 for axis in range(3)),
                index,
            ),
        )
        if selected in used_indices:
            raise ValueError(
                "support particle is reused by multiple anatomical targets: "
                + panel_name
                + " "
                + str(selected)
            )
        used_indices.add(selected)
        selections[str(panel_name)] = selected

    return selections

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Typed defaults shared by headless simulation-quality scene fixtures."""

from typing import TypedDict


class InterClothQualityDefaults(TypedDict):
    """Persistent inter-cloth properties required by simulation-quality test scenes."""

    GarmentGroups: list[str]
    GarmentBodyClearanceByGroup: list[str]
    InterClothClearance: float
    InterClothContactCount: int
    InterClothRemainingContactCount: int
    InterClothCorrectedParticleCount: int
    InterClothMaxPenetration: float
    InterClothResidualPenetration: float


def inter_cloth_quality_defaults() -> InterClothQualityDefaults:
    """Return fresh defaults for the persisted garment-contact scene properties.

    Returns:
        A new set of defaults for use by FreeCAD-compatible scene test doubles.
    """
    return {
        "GarmentGroups": [],
        "GarmentBodyClearanceByGroup": [],
        "InterClothClearance": 1.0,
        "InterClothContactCount": 0,
        "InterClothRemainingContactCount": 0,
        "InterClothCorrectedParticleCount": 0,
        "InterClothMaxPenetration": 0.0,
        "InterClothResidualPenetration": 0.0,
    }

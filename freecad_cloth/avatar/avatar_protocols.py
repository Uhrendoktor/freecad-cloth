# Copyright (C) 2026 FreeCAD Cloth contributors
"""Structural avatar parameter views shared across dependency-sensitive modules."""

from typing import Protocol


class AvatarPoseProtocol(Protocol):
    """Pose fields consumed by the MakeHuman mesh fitter."""

    preset: str
    left_arm_angle: float | None
    right_arm_angle: float | None


class AvatarParametersProtocol(Protocol):
    """Validated avatar parameter fields consumed by mesh providers."""

    measurements: dict[str, float]
    gender: float
    breast_size: float
    skin_offset: float
    phenotype_overrides: dict[str, float]
    local_change_overrides: dict[str, float]
    mass_target_kg: float | None
    pose: AvatarPoseProtocol

    def measurement(self, name: str) -> float:
        """Return one validated anthropometric measurement in millimetres.

        Args:
            name: Canonical measurement key to retrieve.

        Returns:
            The selected measurement value in millimetres.
        """
        ...


class AvatarTaskPanelProtocol(Protocol):
    """Minimal handle for a FreeCAD avatar task panel."""

    form: object

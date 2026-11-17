# Copyright (C) 2026 FreeCAD Cloth contributors
"""Structural avatar parameter views shared across dependency-sensitive modules."""

from typing import Protocol


class AvatarPoseProtocol(Protocol):
    """Read-only pose fields consumed by the MakeHuman mesh fitter."""

    @property
    def preset(self) -> str:
        """Return the stable pose preset identifier."""
        ...

    @property
    def left_arm_angle(self) -> float | None:
        """Return the optional left upper-arm rotation."""
        ...

    @property
    def right_arm_angle(self) -> float | None:
        """Return the optional right upper-arm rotation."""
        ...


class AvatarParametersProtocol(Protocol):
    """Read-only validated avatar parameters consumed by mesh providers."""

    @property
    def measurements(self) -> dict[str, float]:
        """Return the canonical anthropometric measurement mapping."""
        ...

    @property
    def gender(self) -> float:
        """Return the normalized body-shape gender control."""
        ...

    @property
    def breast_size(self) -> float:
        """Return the normalized breast-projection control."""
        ...

    @property
    def skin_offset(self) -> float:
        """Return the collision/skin offset in millimetres."""
        ...

    @property
    def phenotype_overrides(self) -> dict[str, float]:
        """Return the normalized Anny phenotype overrides."""
        ...

    @property
    def local_change_overrides(self) -> dict[str, float]:
        """Return the normalized local body-morph overrides."""
        ...

    @property
    def mass_target_kg(self) -> float | None:
        """Return the optional target body mass."""
        ...

    @property
    def pose(self) -> AvatarPoseProtocol:
        """Return the authored pose contract."""
        ...

    def measurement(self, name: str) -> float:
        """Return one validated anthropometric measurement in millimetres.

        Args:
            name: Canonical measurement key to retrieve.

        Returns:
            The selected measurement value in millimetres.
        """
        ...


class AvatarTaskPanelFormProtocol(Protocol):
    """Visible-widget operations exposed by a FreeCAD avatar task-panel form."""

    def isVisible(self) -> bool:
        """Return whether the task panel form is currently visible.

        Returns:
            True when the form is visible; otherwise False.
        """
        ...

    def show(self) -> None:
        """Show the task panel form."""
        ...

    def setVisible(self, visible: bool) -> None:
        """Set the task panel form's visibility.

        Args:
            visible: True to show the form, or False to hide it.
        """
        ...

    def raise_(self) -> None:
        """Raise the task panel form above peer windows."""
        ...


class AvatarTaskPanelProtocol(Protocol):
    """Minimal handle for a FreeCAD avatar task panel."""

    form: AvatarTaskPanelFormProtocol

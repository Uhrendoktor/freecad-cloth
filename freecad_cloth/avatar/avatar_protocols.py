# Copyright (C) 2026 FreeCAD Cloth contributors
"""Structural avatar parameter views shared across dependency-sensitive modules."""

from collections.abc import Sequence
from typing import Protocol

from freecad_cloth.common.garment_document import (
    FreeCADDocumentObjectProtocol,
    FreeCADDocumentProtocol,
)


class AvatarMeshVectorProtocol(Protocol):
    """Coordinate interface exposed by native FreeCAD mesh vectors."""

    x: float
    y: float
    z: float


class NativeAvatarMeshProtocol(Protocol):
    """Indexed native mesh operations required by the avatar builder."""

    def addFacets(
        self,
        facets: tuple[Sequence[AvatarMeshVectorProtocol], Sequence[Sequence[int]]],
        check_manifold: bool = False,
    ) -> None:
        """Populate the native mesh with shared vertices and indexed faces.

        Args:
            facets: Shared coordinate records and triangle-index sequences.
            check_manifold: Whether FreeCAD should check the supplied topology.
        """
        ...


class AvatarPoseProtocol(Protocol):
    """Read-only pose fields consumed by the MakeHuman mesh fitter."""

    @property
    def preset(self) -> str:
        """Return the stable pose preset identifier.

        Returns:
            Canonical identifier of the current pose preset.
        """
        ...

    @property
    def left_arm_angle(self) -> float | None:
        """Return the optional left upper-arm rotation.

        Returns:
            Left arm angle in degrees, or None when not specified.
        """
        ...

    @property
    def right_arm_angle(self) -> float | None:
        """Return the optional right upper-arm rotation.

        Returns:
            Right arm angle in degrees, or None when not specified.
        """
        ...


class AvatarParametersProtocol(Protocol):
    """Read-only validated avatar parameters consumed by mesh providers."""

    @property
    def measurements(self) -> dict[str, float]:
        """Return the canonical anthropometric measurement mapping.

        Returns:
            Measurement names mapped to values in millimetres.
        """
        ...

    @property
    def gender(self) -> float:
        """Return the normalized body-shape gender control.

        Returns:
            Body-shape blend in the closed interval from zero to one.
        """
        ...

    @property
    def breast_size(self) -> float:
        """Return the normalized breast-projection control.

        Returns:
            Breast fullness in the closed interval from zero to one.
        """
        ...

    @property
    def skin_offset(self) -> float:
        """Return the collision/skin offset in millimetres.

        Returns:
            Configured offset in millimetres.
        """
        ...

    @property
    def phenotype_overrides(self) -> dict[str, float]:
        """Return the normalized Anny phenotype overrides.

        Returns:
            Phenotype names mapped to normalized values.
        """
        ...

    @property
    def local_change_overrides(self) -> dict[str, float]:
        """Return the normalized local body-morph overrides.

        Returns:
            Morph labels mapped to signed local-change values.
        """
        ...

    @property
    def mass_target_kg(self) -> float | None:
        """Return the optional target body mass.

        Returns:
            Target mass in kilograms, or None when mass fitting is disabled.
        """
        ...

    @property
    def pose(self) -> AvatarPoseProtocol:
        """Return the authored pose contract.

        Returns:
            Read-only pose settings used by mesh generation.
        """
        ...

    def measurement(self, name: str) -> float:
        """Return one validated anthropometric measurement in millimetres.

        Args:
            name: Canonical measurement key to retrieve.

        Returns:
            The selected measurement value in millimetres.
        """
        ...


class AvatarParametersFeatureProtocol(FreeCADDocumentObjectProtocol, Protocol):
    """Persistent avatar properties required to reconstruct validated parameters."""

    @property
    def Document(self) -> FreeCADDocumentProtocol:
        """Return the document that owns the persistent avatar feature."""
        ...

    PosePreset: str
    JointPoseJSON: str
    ParametersJSON: str
    SkinOffset: float


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

    @property
    def form(self) -> AvatarTaskPanelFormProtocol:
        """Return the native Qt form owned by the task panel.

        Returns:
            Visible form exposing the task-panel lifecycle operations.
        """
        ...

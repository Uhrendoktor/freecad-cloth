# Copyright (C) 2026 FreeCAD Cloth contributors
"""Replaceable, typed avatar-provider boundary for fitting and simulation.

A provider supplies authoritative parameters when available, a visual mesh,
a neutral collision surface, and semantic landmarks. It does not leak native
FreeCAD document implementation or solver details to downstream callers.
"""

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Landmark
from freecad_cloth.avatar.AvatarService import AvatarService, AvatarSurface
from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.common.ValidationModels import validate_finite_number
from freecad_cloth.shared.Collision import CollisionSurface, surface_from_triangles


@pydantic_dataclass(frozen=True)
class AvatarProviderInfo:
    """Persistent identity presented by the avatar UI and document layer."""

    provider_id: str
    display_name: str
    fidelity: str


class AvatarProvider:
    """Structural contract consumed by fitting and simulation adapters."""

    info: AvatarProviderInfo = AvatarProviderInfo("unknown", "Unknown", "unknown")

    def parameters(self) -> AvatarParameters | None:
        """Return authoritative anthropometric parameters when available.

        Returns:
            Canonical parameters, or None for imported geometry without controls.

        Raises:
            NotImplementedError: If a concrete provider omits this operation.
        """
        raise NotImplementedError

    def surface(self) -> AvatarSurface:
        """Return the visual mesh in millimetres.

        Returns:
            Immutable vertices and corresponding triangle indices.

        Raises:
            NotImplementedError: If a concrete provider omits this operation.
        """
        raise NotImplementedError

    def collision_surface(self) -> CollisionSurface:
        """Return a validated, host-neutral collision surface.

        Returns:
            Collision geometry for fitting and simulation.

        Raises:
            NotImplementedError: If a concrete provider omits this operation.
        """
        raise NotImplementedError

    def landmarks(self) -> tuple[Landmark, ...]:
        """Return stable semantic landmarks when the provider defines them.

        Returns:
            Named landmark coordinates, or an empty tuple if unavailable.

        Raises:
            NotImplementedError: If a concrete provider omits this operation.
        """
        raise NotImplementedError


class ParametricAvatarProvider(AvatarProvider):
    """Built-in anthropometric provider backed by the pinned MakeHuman mesh."""

    info = AvatarProviderInfo("makehuman-hm08", "MakeHuman HM08 humanoid mesh", "high")

    def __init__(self, parameters: AvatarParameters | None = None) -> None:
        """Create the mannequin provider for a canonical parameter state.

        Args:
            parameters: Optional avatar settings; omitted values use defaults.

        Raises:
            TypeError: If parameters is not an AvatarParameters instance.
        """
        self._service = AvatarService(parameters)

    def parameters(self) -> AvatarParameters:
        """Return the current provider parameters.

        Returns:
            The canonical immutable avatar parameter state.
        """
        return self._service.parameters()

    def surface(self) -> AvatarSurface:
        """Return the current MakeHuman visual mesh.

        Returns:
            Vertices and triangle indices in Cloth millimetre coordinates.
        """
        return self._service.surface()

    def collision_surface(self) -> CollisionSurface:
        """Return the neutral collision contract for the mannequin.

        Returns:
            A validated collision surface derived from the same mesh as surface().
        """
        vertices, triangles = self._service.collision_mesh()
        return surface_from_triangles(vertices, triangles, region="avatar")

    def landmarks(self) -> tuple[Landmark, ...]:
        """Return stable mannequin landmarks.

        Returns:
            Named points used by fitting and pose visualization.
        """
        return self._service.landmarks()


class FreeCADGeometryAvatarProvider(AvatarProvider):
    """Adapter for an imported or native FreeCAD body.

    Collision tessellation is delegated to the shared FreeCAD surface adapter
    so downstream code does not branch on Part, PartDesign, or Mesh objects.
    """

    info = AvatarProviderInfo("freecad-geometry", "FreeCAD body", "external")

    def __init__(
        self,
        source: object | None,
        deflection: float = 1.0,
        thickness: float = 0.0,
    ) -> None:
        """Create an adapter for an imported FreeCAD geometry object.

        Args:
            source: Shape or mesh object supplying the surface tessellation.
            deflection: Maximum tessellation deviation in millimetres.
            thickness: Non-negative collision padding in millimetres.

        Raises:
            ValueError: If source is missing or either numeric setting is invalid.
        """
        if source is None:
            msg = "a FreeCAD geometry avatar provider requires a source"
            raise ValueError(msg)
        self.source = source
        self.deflection = validate_finite_number(deflection)
        self.thickness = validate_finite_number(thickness)
        if self.deflection <= 0.0:
            msg = "deflection must be positive and finite"
            raise ValueError(msg)
        if self.thickness < 0.0:
            msg = "thickness must be non-negative and finite"
            raise ValueError(msg)

    def parameters(self) -> None:
        """Report that imported geometry has no mannequin parameter controls.

        Returns:
            None, because the source object's geometry is authoritative.
        """
        return None

    def surface(self) -> AvatarSurface:
        """Return the imported geometry as an immutable mesh.

        Returns:
            Tessellated vertices and triangle indices in millimetres.

        Raises:
            ValueError: If the FreeCAD object has no valid triangle surface.
        """
        surface = surface_from_freecad(self.source, self.deflection, self.thickness)
        return surface.vertices, surface.triangles

    def collision_surface(self) -> CollisionSurface:
        """Return collision tessellation through the shared FreeCAD adapter.

        Returns:
            A validated host-neutral collision surface.
        """
        return surface_from_freecad(self.source, self.deflection, self.thickness)

    def landmarks(self) -> tuple[Landmark, ...]:
        """Return no semantic landmarks for arbitrary imported geometry.

        Returns:
            An empty tuple because the adapter cannot infer human joint names.
        """
        return ()


# Provider metadata is the single source of IDs shown in the persisted selector.
BUILTIN_AVATAR_PROVIDER_CLASSES = (
    ParametricAvatarProvider,
    FreeCADGeometryAvatarProvider,
)
PROVIDER_IDS = tuple(provider.info.provider_id for provider in BUILTIN_AVATAR_PROVIDER_CLASSES)
PARAMETRIC_PROVIDER_ID = ParametricAvatarProvider.info.provider_id
FREECAD_GEOMETRY_PROVIDER_ID = FreeCADGeometryAvatarProvider.info.provider_id


def provider_from_target(
    source: object | None,
    target_type: str = "FreeCAD Geometry",
    parameters: AvatarParameters | None = None,
    deflection: float = 1.0,
    thickness: float = 0.0,
) -> AvatarProvider:
    """Select a built-in provider from the persisted target type.

    Args:
        source: Optional FreeCAD object used by the imported-geometry provider.
        target_type: User-facing target kind selected in the document.
        parameters: Canonical mannequin parameters, used only for mannequin targets.
        deflection: Maximum tessellation deviation in millimetres.
        thickness: Non-negative collision padding in millimetres.

    Returns:
        The matching concrete avatar provider.

    Raises:
        ValueError: If target_type is unsupported or its source/settings are invalid.
    """
    kind = str(target_type)
    if kind == "Mannequin":
        return ParametricAvatarProvider(parameters)
    if kind == "FreeCAD Geometry":
        return FreeCADGeometryAvatarProvider(source, deflection, thickness)
    msg = f"unsupported avatar provider target type: {kind}"
    raise ValueError(msg)

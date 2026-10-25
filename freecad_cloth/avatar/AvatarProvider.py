# Copyright (C) 2026 FreeCAD Cloth contributors
"""Replaceable avatar-provider contract for the Cloth fitting/simulation stack.

The provider boundary knows nothing about FreeCAD document implementation or
solver details. A provider supplies authoritative parameters, a visual/collision
surface and stable landmarks. The built-in human provider uses a real MakeHuman
HM08 polygon mesh; a CAD provider adapts an existing FreeCAD object.
"""

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.avatar.AvatarService import AvatarService
from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.shared.Collision import surface_from_triangles


@pydantic_dataclass(frozen=True)
class AvatarProviderInfo:
    """Persistent identity presented by the avatar UI/document layer."""

    provider_id: str
    display_name: str
    fidelity: str


class AvatarProvider:
    """Minimal provider protocol consumed by fitting and target adapters."""

    info = AvatarProviderInfo("unknown", "Unknown", "unknown")

    def parameters(self):
        """Return the current provider parameters."""
        raise NotImplementedError

    def surface(self):
        """Return the current surface mesh."""
        raise NotImplementedError

    def collision_surface(self):
        """Return a collision-ready surface representation."""
        raise NotImplementedError

    def landmarks(self):
        """Return the semantic avatar landmarks."""
        raise NotImplementedError


class ParametricAvatarProvider(AvatarProvider):
    """Built-in anthropometric provider backed by the real MakeHuman mesh."""

    info = AvatarProviderInfo("makehuman-hm08", "MakeHuman HM08 humanoid mesh", "high")

    def __init__(self, parameters=None):
        self._service = AvatarService(parameters)

    def parameters(self):
        """Return the current provider parameters."""
        return self._service.parameters()

    def surface(self):
        """Return the current surface mesh."""
        return self._service.surface()

    def collision_surface(self):
        """Return the neutral collision-surface contract."""
        vertices, triangles = self._service.collision_mesh()
        return surface_from_triangles(vertices, triangles, region="avatar")

    def landmarks(self):
        """Return the semantic avatar landmarks."""
        return self._service.landmarks()


class FreeCADGeometryAvatarProvider(AvatarProvider):
    """Adapter for an imported/native FreeCAD body without a hard dependency.

    Collision tessellation is delegated to the existing DrapeTarget surface
    adapter, so Sewing and Simulation do not need to know whether the body came
    from Part, PartDesign, or Mesh.
    """

    info = AvatarProviderInfo("freecad-geometry", "FreeCAD body", "external")

    def __init__(self, source, deflection=1.0, thickness=0.0):
        if source is None:
            msg = "a FreeCAD geometry avatar provider requires a source"
            raise ValueError(msg)
        self.source = source
        self.deflection = float(deflection)
        self.thickness = float(thickness)
        if self.deflection <= 0:
            msg = "deflection must be positive"
            raise ValueError(msg)
        if self.thickness < 0:
            msg = "thickness must not be negative"
            raise ValueError(msg)

    def parameters(self):
        """Return the current provider parameters."""
        return

    def surface(self):
        """Return the current surface mesh."""
        surface = surface_from_freecad(self.source, self.deflection, self.thickness)
        return surface.vertices, surface.triangles

    def collision_surface(self):
        """Return the neutral collision-surface contract."""
        return surface_from_freecad(self.source, self.deflection, self.thickness)

    def landmarks(self):
        """Return the semantic avatar landmarks."""
        return ()


# Single source of truth for built-in providers exposed by the persistent selector.
BUILTIN_AVATAR_PROVIDER_CLASSES = (
    ParametricAvatarProvider,
    FreeCADGeometryAvatarProvider,
)

PROVIDER_IDS = tuple(provider.info.provider_id for provider in BUILTIN_AVATAR_PROVIDER_CLASSES)
PARAMETRIC_PROVIDER_ID = ParametricAvatarProvider.info.provider_id
FREECAD_GEOMETRY_PROVIDER_ID = FreeCADGeometryAvatarProvider.info.provider_id


def provider_from_target(
    source, target_type="FreeCAD Geometry", parameters=None, deflection=1.0, thickness=0.0
):
    """Build the appropriate provider without coupling callers to a class."""
    kind = str(target_type)
    if kind == "Mannequin":
        return ParametricAvatarProvider(parameters)
    if kind == "FreeCAD Geometry":
        return FreeCADGeometryAvatarProvider(source, deflection, thickness)
    msg = f"unsupported avatar provider target type: {kind}"
    raise ValueError(msg)

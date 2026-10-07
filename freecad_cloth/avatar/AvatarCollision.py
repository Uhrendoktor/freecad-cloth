"""Compatibility exports for avatar collision adapters.

The collision geometry value type is neutral and lives in shared.collision.
FreeCAD conversion remains a host adapter so Simulation never depends on Avatar.
"""

from dataclasses import dataclass

from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.shared.collision import (
    CollisionSurface,
    surface_from_triangles,
)


def ensure_collision_proxy(doc, source_obj, thickness=2.0, deflection=1.0):
    """Create or refresh the legacy avatar collision display proxy locally."""
    avatar = doc.getObject("AvatarCollision")
    if avatar is None:
        avatar = doc.addObject("App::FeaturePython", "AvatarCollision")
        avatar.Label = "Avatar Collision Proxy (Compatibility)"
        avatar.addProperty("App::PropertyString", "CollisionType", "Simulation")
        avatar.addProperty("App::PropertyLink", "SourceObject", "Simulation")
        avatar.addProperty("App::PropertyFloat", "CollisionThickness", "Simulation")
        avatar.addProperty("App::PropertyFloat", "CollisionDeflection", "Simulation")
        avatar.addProperty("App::PropertyInteger", "CollisionVertexCount", "Simulation")
        avatar.addProperty("App::PropertyInteger", "CollisionTriangleCount", "Simulation")
    surface = surface_from_freecad(source_obj, float(deflection), float(thickness))
    avatar.SourceObject = source_obj
    avatar.CollisionType = "MeshSurface"
    avatar.CollisionThickness = float(thickness)
    avatar.CollisionDeflection = float(deflection)
    avatar.CollisionVertexCount = len(surface.vertices)
    avatar.CollisionTriangleCount = len(surface.triangles)
    return avatar


@dataclass(frozen=True)
class AvatarSpec:
    """Host-neutral avatar identity and optional collision surface."""

    name: str
    unit: str = "mm"
    coordinate_system: str = "RH-Z-up"
    collision: CollisionSurface | None = None

    def validate(self) -> "AvatarSpec":
        """Validate identity and coordinate conventions."""
        if not self.name.strip() or self.unit not in {"mm", "cm", "m"}:
            raise ValueError("invalid avatar identity or units")
        if self.coordinate_system != "RH-Z-up":
            raise ValueError("unsupported coordinate convention")
        if self.collision is not None:
            self.collision.validate()
        return self

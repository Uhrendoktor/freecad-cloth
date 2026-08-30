"""Target-neutral draping/collision contract.

The solver consumes a :class:`CollisionSurface`; this module owns the small
FreeCAD-facing distinction between a human mannequin and arbitrary CAD/Mesh
geometry.  The pure data model deliberately has no FreeCAD dependency so it
can be regression-tested without a FreeCAD installation.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from AvatarCollision import CollisionSurface, surface_from_freecad


@dataclass(frozen=True)
class DrapeTargetSpec:
    """Persistent target settings independent of a FreeCAD document object."""

    target_type: str = "FreeCAD Geometry"
    source_name: str = ""
    deflection: float = 1.0
    thickness: float = 0.0
    enabled: bool = True

    VALID_TYPES = ("Mannequin", "FreeCAD Geometry")

    def validate(self) -> None:
        if self.target_type not in self.VALID_TYPES:
            raise ValueError("unsupported drape target type")
        if not self.source_name.strip():
            raise ValueError("drape target source must not be empty")
        if self.deflection <= 0:
            raise ValueError("drape target deflection must be positive")
        if self.thickness < 0:
            raise ValueError("drape target thickness must not be negative")


def collision_surface(target, deflection: float = 1.0, thickness: float = 0.0) -> CollisionSurface:
    """Resolve a FreeCAD Shape/Mesh target through the common adapter."""
    return surface_from_freecad(target, float(deflection), float(thickness))


def source_signature(target, deflection: float = 1.0, thickness: float = 0.0) -> Tuple:
    """Return deterministic target inputs used to invalidate derived scenes.

    Placement is included when available.  The actual shape/mesh conversion
    remains lazy; callers can cheaply compare this signature before rebuilding.
    """
    placement = getattr(target, "Placement", None)
    base = getattr(placement, "Base", None) if placement is not None else None
    rotation = getattr(placement, "Rotation", None) if placement is not None else None
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        str(getattr(target, "Name", "")),
        str(getattr(target, "Label", "")),
        float(getattr(base, "x", 0.0)),
        float(getattr(base, "y", 0.0)),
        float(getattr(base, "z", 0.0)),
        float(getattr(rotation, "Angle", 0.0)) if rotation is not None else 0.0,
        float(getattr(axis, "x", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "y", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "z", 1.0)) if axis is not None else 1.0,
        float(deflection),
        float(thickness),
    )


def create_drape_target(doc, source=None, target_type: str = "FreeCAD Geometry",
                        deflection: float = 1.0, thickness: float = 0.0):
    """Create a persistent FreeCAD DrapeTarget linked to ``source``.

    ``source`` may be omitted only for a mannequin target; in that case the
    caller is expected to assign a mannequin object before recompute.  The
    target object intentionally stores a Link rather than copying geometry.
    """
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        raise ValueError("unsupported drape target type")
    if deflection <= 0 or thickness < 0:
        raise ValueError("invalid collision tessellation or thickness")
    if source is None and target_type != "Mannequin":
        raise ValueError("a FreeCAD Geometry target requires a source object")

    target = doc.addObject("App::FeaturePython", "DrapeTarget")
    target.Label = "Drape Target"
    target.addProperty("App::PropertyString", "TargetType", "Draping")
    target.addProperty("App::PropertyLink", "SourceObject", "Draping")
    target.addProperty("App::PropertyFloat", "CollisionDeflection", "Collision")
    target.addProperty("App::PropertyFloat", "CollisionThickness", "Collision")
    target.addProperty("App::PropertyBool", "Enabled", "Draping")
    target.addProperty("App::PropertyString", "SourceSignature", "State")
    target.TargetType = target_type
    target.CollisionDeflection = float(deflection)
    target.CollisionThickness = float(thickness)
    target.Enabled = True
    if source is not None:
        target.SourceObject = source
        target.SourceSignature = repr(source_signature(source, deflection, thickness))
        surface = collision_surface(source, deflection, thickness)
        target.CollisionVertexCount = len(surface.vertices) if hasattr(target, "CollisionVertexCount") else 0
    return target


def assign_drape_target(target, source, target_type: Optional[str] = None):
    """Update an existing persistent target without copying source geometry."""
    if source is None:
        raise ValueError("drape target source is required")
    kind = str(target_type or getattr(target, "TargetType", "FreeCAD Geometry"))
    if kind not in DrapeTargetSpec.VALID_TYPES:
        raise ValueError("unsupported drape target type")
    deflection = float(getattr(target, "CollisionDeflection", 1.0))
    thickness = float(getattr(target, "CollisionThickness", 0.0))
    surface = collision_surface(source, deflection, thickness)
    target.TargetType = kind
    target.SourceObject = source
    target.SourceSignature = repr(source_signature(source, deflection, thickness))
    if hasattr(target, "CollisionVertexCount"):
        target.CollisionVertexCount = len(surface.vertices)
    if hasattr(target, "CollisionTriangleCount"):
        target.CollisionTriangleCount = len(surface.triangles)
    return target

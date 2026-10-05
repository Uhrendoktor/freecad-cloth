"""Target-neutral draping/collision contract."""

from dataclasses import dataclass

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, surface_from_freecad
from freecad_cloth.shared.SourceSignature import source_signature


@dataclass(frozen=True)
class DrapeTargetSpec:
    """Public data model or service class for DrapeTargetSpec."""

    target_type: str
    source_name: str
    deflection: float = 1.0
    thickness: float = 0.0

    VALID_TYPES = ("Mannequin", "FreeCAD Geometry")

    def validate(self):
        """Validate this value and raise ValueError when its state is invalid."""
        if self.target_type not in self.VALID_TYPES:
            raise ValueError("unsupported drape target type")
        if not self.source_name.strip():
            raise ValueError("drape target source must not be empty")
        if self.deflection <= 0:
            raise ValueError("drape target deflection must be positive")
        if self.thickness < 0:
            raise ValueError("drape target thickness must not be negative")


def collision_surface(target, deflection=1.0, thickness=0.0) -> CollisionSurface:
    """Return a collision-ready surface representation."""
    return surface_from_freecad(target, float(deflection), float(thickness))


def target_status(target):
    """Return a deterministic user-facing state for a persistent DrapeTarget."""
    if target is None:
        return {
            "state": "missing",
            "message": "No drape target selected",
            "stale": True,
            "reason": "target missing",
        }
    if not bool(getattr(target, "Enabled", True)):
        return {
            "state": "disabled",
            "message": "Drape target is disabled",
            "stale": False,
            "reason": "target disabled",
        }
    target_type = str(getattr(target, "TargetType", ""))
    source = getattr(target, "SourceObject", None)
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        return {
            "state": "invalid",
            "message": "Unsupported drape target type",
            "stale": True,
            "reason": "unsupported target type",
        }
    if source is None:
        message = (
            "Mannequin target has no source object"
            if target_type == "Mannequin"
            else "FreeCAD Geometry target has no source object"
        )
        return {
            "state": "unassigned",
            "message": message,
            "stale": True,
            "reason": "source missing",
        }
    vertices = int(getattr(target, "CollisionVertexCount", 0))
    triangles = int(getattr(target, "CollisionTriangleCount", 0))
    if not getattr(target, "SourceSignature", "") or vertices <= 0 or triangles <= 0:
        return {
            "state": "unbuilt",
            "message": "Drape target collision surface needs to be built",
            "stale": True,
            "reason": "collision cache missing",
        }
    try:
        current = repr(
            source_signature(
                source,
                float(getattr(target, "CollisionDeflection", 1.0)),
                float(getattr(target, "CollisionThickness", 0.0)),
            )
        )
    except (AttributeError, TypeError, ValueError) as exc:
        return {
            "state": "invalid",
            "message": f"Cannot inspect drape target: {exc}",
            "stale": True,
            "reason": "signature failed",
        }
    authored = str(getattr(target, "SourceSignature", ""))
    if current != authored:
        return {
            "state": "stale",
            "message": "Drape target changed; rebuild collision surface before simulation",
            "stale": True,
            "reason": "source, placement, tessellation or collision thickness changed",
            "signature_current": current,
            "signature_authored": authored,
        }
    return {
        "state": "ready",
        "message": "Drape target collision surface is current",
        "stale": False,
        "reason": "",
    }


def refresh_drape_target(target):
    """Provide the public refresh drape target operation."""
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target source is required")
    return assign_drape_target(target, source, getattr(target, "TargetType", "FreeCAD Geometry"))


def create_drape_target(
    doc, source=None, target_type="FreeCAD Geometry", deflection=1.0, thickness=0.0
):
    """Create and return the requested drape target object."""
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        raise ValueError("unsupported drape target type")
    if deflection <= 0 or thickness < 0:
        raise ValueError("invalid collision tessellation or thickness")
    if source is None and target_type != "Mannequin":
        raise ValueError("a FreeCAD Geometry target requires a source object")
    target = doc.addObject("App::FeaturePython", "DrapeTarget")
    target.Label = "Drape Target"
    for type_name, name, group in (
        ("App::PropertyString", "TargetType", "Draping"),
        ("App::PropertyLink", "SourceObject", "Draping"),
        ("App::PropertyFloat", "CollisionDeflection", "Collision"),
        ("App::PropertyFloat", "CollisionThickness", "Collision"),
        ("App::PropertyBool", "Enabled", "Draping"),
        ("App::PropertyInteger", "CollisionVertexCount", "State"),
        ("App::PropertyInteger", "CollisionTriangleCount", "State"),
        ("App::PropertyString", "SourceSignature", "State"),
        ("App::PropertyString", "TargetStatus", "State"),
        ("App::PropertyString", "InvalidationReason", "State"),
    ):
        target.addProperty(type_name, name, group)
    target.TargetType = target_type
    target.CollisionDeflection = float(deflection)
    target.CollisionThickness = float(thickness)
    target.Enabled = True
    target.CollisionVertexCount = 0
    target.CollisionTriangleCount = 0
    target.TargetStatus = "unassigned"
    target.InvalidationReason = "collision cache missing"
    if source is not None:
        assign_drape_target(target, source, target_type)
    from freecad_cloth.common.GarmentDocument import link_garment_object

    link_garment_object(target, "DrapeTarget", doc)
    return target


def assign_drape_target(target, source, target_type: str | None = None):
    """Provide the public assign drape target operation."""
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
    target.CollisionVertexCount = len(surface.vertices)
    target.CollisionTriangleCount = len(surface.triangles)
    status = target_status(target)
    target.TargetStatus = status["state"]
    target.InvalidationReason = status["reason"]
    return target


from freecad_cloth.simulation.SimulationStaleGuard import install as _install_simulation_guard

_install_simulation_guard()

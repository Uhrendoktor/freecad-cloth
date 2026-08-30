"""Target-neutral draping/collision contract and persistent lifecycle state."""
from dataclasses import dataclass
import hashlib
from typing import Optional, Tuple
from AvatarCollision import CollisionSurface, surface_from_freecad


@dataclass(frozen=True)
class DrapeTargetSpec:
    target_type: str = "FreeCAD Geometry"
    source_name: str = ""
    deflection: float = 1.0
    thickness: float = 0.0
    enabled: bool = True
    VALID_TYPES = ("Mannequin", "FreeCAD Geometry")

    def validate(self):
        if self.target_type not in self.VALID_TYPES: raise ValueError("unsupported drape target type")
        if not self.source_name.strip(): raise ValueError("drape target source must not be empty")
        if self.deflection <= 0: raise ValueError("drape target deflection must be positive")
        if self.thickness < 0: raise ValueError("drape target thickness must not be negative")


STATES = ("VALID", "STALE", "INVALID", "REFRESHING", "READY_FOR_SIMULATION")


def collision_surface(target, deflection=1.0, thickness=0.0) -> CollisionSurface:
    return surface_from_freecad(target, float(deflection), float(thickness))


def _geometry_signature(target):
    shape = getattr(target, "Shape", None)
    if shape is not None:
        try:
            if not shape.isNull(): return ("Shape", int(shape.hashCode()))
        except (AttributeError, TypeError, ValueError): pass
    mesh = getattr(target, "Mesh", None)
    if mesh is not None:
        topology = getattr(mesh, "Topology", None)
        if topology is not None:
            try:
                vertices, triangles = topology
                return ("Mesh", len(vertices), len(triangles))
            except (TypeError, ValueError): pass
    return ("Unknown",)


def source_signature(target, deflection=1.0, thickness=0.0) -> Tuple:
    placement = getattr(target, "Placement", None)
    base = getattr(placement, "Base", None) if placement is not None else None
    rotation = getattr(placement, "Rotation", None) if placement is not None else None
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (str(getattr(target, "Name", "")), str(getattr(target, "Label", "")), _geometry_signature(target),
            float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)),
            float(getattr(rotation, "Angle", 0.0)) if rotation is not None else 0.0,
            float(getattr(axis, "x", 0.0)) if axis is not None else 0.0,
            float(getattr(axis, "y", 0.0)) if axis is not None else 0.0,
            float(getattr(axis, "z", 1.0)) if axis is not None else 1.0,
            float(deflection), float(thickness))


def _digest(signature):
    return hashlib.sha256(repr(signature).encode("utf-8")).hexdigest()


def _state(target, lifecycle, message, reason=""):
    return {
        "state": {"VALID": "valid", "STALE": "stale", "INVALID": "invalid", "REFRESHING": "refreshing", "READY_FOR_SIMULATION": "ready"}[lifecycle],
        "lifecycle_state": lifecycle,
        "message": message,
        "stale": lifecycle in ("STALE", "INVALID", "REFRESHING"),
        "reason": reason,
    }


def target_status(target):
    """Return a deterministic user-facing state for a persistent DrapeTarget."""
    if target is None:
        return _state(target, "INVALID", "No drape target selected", "target missing")
    if not bool(getattr(target, "Enabled", True)):
        return _state(target, "INVALID", "Drape target is disabled", "target disabled")
    source = getattr(target, "SourceObject", None)
    target_type = str(getattr(target, "TargetType", "FreeCAD Geometry"))
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        return _state(target, "INVALID", "Unsupported drape target type", "unsupported target type")
    if source is None:
        return _state(target, "STALE", "Drape target has no source object", "source missing")
    try:
        current_signature = source_signature(source, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0)))
        current = repr(current_signature)
    except (AttributeError, TypeError, ValueError) as exc:
        return _state(target, "INVALID", "Cannot inspect drape target source: %s" % exc, "source inspection failed")
    vertices = int(getattr(target, "CollisionVertexCount", 0))
    triangles = int(getattr(target, "CollisionTriangleCount", 0))
    authored = str(getattr(target, "SourceSignature", ""))
    if not authored or vertices <= 0 or triangles <= 0:
        return _state(target, "STALE", "Drape target collision surface needs to be refreshed", "collision cache missing")
    if current != authored:
        return _state(target, "STALE", "Drape target changed; refresh before simulation", "source geometry, placement or collision parameters changed")
    lifecycle = str(getattr(target, "LifecycleState", "READY_FOR_SIMULATION"))
    if lifecycle == "REFRESHING":
        return _state(target, lifecycle, "Drape target is refreshing", str(getattr(target, "InvalidationReason", "")))
    return _state(target, "READY_FOR_SIMULATION", "Drape target collision surface is current", "")


def refresh_drape_target(target):
    """Rebuild persistent collision metadata and return a simulation-ready target."""
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target source is required")
    if hasattr(target, "LifecycleState"):
        target.LifecycleState = "REFRESHING"
        target.TargetStatus = "REFRESHING"
        target.InvalidationReason = "explicit refresh"
    result = assign_drape_target(target, source, getattr(target, "TargetType", "FreeCAD Geometry"))
    if hasattr(target, "LifecycleState"):
        target.LifecycleState = "READY_FOR_SIMULATION"
        target.TargetStatus = "READY_FOR_SIMULATION"
        target.InvalidationReason = ""
    return result


def invalidate_drape_target(target, reason):
    if target is None:
        return None
    if hasattr(target, "LifecycleState"):
        target.LifecycleState = "STALE"
        target.TargetStatus = "STALE"
        target.InvalidationReason = str(reason).strip() or "dependency changed"
    return target


def create_drape_target(doc, source=None, target_type="FreeCAD Geometry", deflection=1.0, thickness=0.0):
    if target_type not in DrapeTargetSpec.VALID_TYPES: raise ValueError("unsupported drape target type")
    if deflection <= 0 or thickness < 0: raise ValueError("invalid collision tessellation or thickness")
    if source is None and target_type != "Mannequin": raise ValueError("a FreeCAD Geometry target requires a source object")
    target = doc.addObject("App::FeaturePython", "DrapeTarget")
    target.Label = "Drape Target"
    target.addProperty("App::PropertyString", "TargetType", "Draping")
    target.addProperty("App::PropertyLink", "SourceObject", "Draping")
    target.addProperty("App::PropertyFloat", "CollisionDeflection", "Collision")
    target.addProperty("App::PropertyFloat", "CollisionThickness", "Collision")
    target.addProperty("App::PropertyBool", "Enabled", "Draping")
    target.addProperty("App::PropertyInteger", "CollisionVertexCount", "State")
    target.addProperty("App::PropertyInteger", "CollisionTriangleCount", "State")
    target.addProperty("App::PropertyString", "SourceSignature", "State")
    target.addProperty("App::PropertyEnumeration", "LifecycleState", "State")
    target.addProperty("App::PropertyString", "TargetStatus", "State")
    target.addProperty("App::PropertyString", "InvalidationReason", "State")
    target.LifecycleState = list(STATES)
    target.LifecycleState = "STALE"
    target.TargetType = target_type
    target.CollisionDeflection = float(deflection)
    target.CollisionThickness = float(thickness)
    target.Enabled = True
    target.CollisionVertexCount = 0
    target.CollisionTriangleCount = 0
    target.TargetStatus = "STALE"
    target.InvalidationReason = "collision cache missing"
    if source is not None:
        assign_drape_target(target, source, target_type)
    return target


def assign_drape_target(target, source, target_type: Optional[str] = None):
    if source is None: raise ValueError("drape target source is required")
    kind = str(target_type or getattr(target, "TargetType", "FreeCAD Geometry"))
    if kind not in DrapeTargetSpec.VALID_TYPES: raise ValueError("unsupported drape target type")
    deflection = float(getattr(target, "CollisionDeflection", 1.0))
    thickness = float(getattr(target, "CollisionThickness", 0.0))
    surface = collision_surface(source, deflection, thickness)
    target.TargetType = kind
    target.SourceObject = source
    target.SourceSignature = repr(source_signature(source, deflection, thickness))
    target.CollisionVertexCount = len(surface.vertices)
    target.CollisionTriangleCount = len(surface.triangles)
    if hasattr(target, "LifecycleState"):
        target.LifecycleState = "READY_FOR_SIMULATION"
        target.TargetStatus = "READY_FOR_SIMULATION"
        target.InvalidationReason = ""
    else:
        status = target_status(target)
        target.TargetStatus = status["state"]
        target.InvalidationReason = status["reason"]
    return target

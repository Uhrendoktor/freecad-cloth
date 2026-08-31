"""Target-neutral draping/collision contract.

The solver consumes a CollisionSurface; this module owns the persistent
FreeCAD-facing distinction between a mannequin and arbitrary CAD/Mesh geometry.
The data contract remains FreeCAD-independent so it can be tested headlessly.
"""
from dataclasses import dataclass
from typing import Optional, Tuple
from freecad_cloth.avatar.AvatarCollision import CollisionSurface, surface_from_freecad


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


def target_status(target):
    """Return a deterministic user-facing state for a persistent DrapeTarget.

    ``stale`` means the authored source/placement/tessellation inputs changed
    since the target's collision cache was last built. It is intentionally
    separate from ``invalid`` so the Simulation workbench can request a rebuild
    instead of silently continuing with stale collision geometry.
    """
    if target is None:
        return {"state": "missing", "message": "No drape target selected", "stale": True, "reason": "target missing"}
    if not bool(getattr(target, "Enabled", True)):
        return {"state": "disabled", "message": "Drape target is disabled", "stale": False, "reason": "target disabled"}
    source = getattr(target, "SourceObject", None)
    target_type = str(getattr(target, "TargetType", "FreeCAD Geometry"))
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        return {"state": "invalid", "message": "Unsupported drape target type", "stale": True, "reason": "unsupported target type"}
    if source is None:
        if target_type == "Mannequin":
            return {"state": "unassigned", "message": "Mannequin target has no source object", "stale": True, "reason": "source missing"}
        return {"state": "unassigned", "message": "FreeCAD Geometry target has no source object", "stale": True, "reason": "source missing"}
    try:
        current = repr(source_signature(source, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0))))
    except (AttributeError, TypeError, ValueError) as exc:
        return {"state": "invalid", "message": "Cannot inspect drape target source: %s" % exc, "stale": True, "reason": "source inspection failed"}
    authored = str(getattr(target, "SourceSignature", ""))
    vertices = int(getattr(target, "CollisionVertexCount", 0))
    triangles = int(getattr(target, "CollisionTriangleCount", 0))
    if not authored or vertices <= 0 or triangles <= 0:
        return {"state": "unbuilt", "message": "Drape target collision surface needs to be built", "stale": True, "reason": "collision cache missing"}
    if current != authored:
        return {"state": "stale", "message": "Drape target changed; rebuild collision surface before simulation", "stale": True, "reason": "source, placement, tessellation or collision thickness changed"}
    return {"state": "ready", "message": "Drape target collision surface is current", "stale": False, "reason": ""}


def refresh_drape_target(target):
    """Rebuild the persistent collision metadata from the current source."""
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target source is required")
    return assign_drape_target(target, source, getattr(target, "TargetType", "FreeCAD Geometry"))


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
    target.addProperty("App::PropertyString", "TargetStatus", "State")
    target.addProperty("App::PropertyString", "InvalidationReason", "State")
    target.TargetType=target_type; target.CollisionDeflection=float(deflection); target.CollisionThickness=float(thickness); target.Enabled=True; target.CollisionVertexCount=0; target.CollisionTriangleCount=0
    target.TargetStatus="unassigned"; target.InvalidationReason="collision cache missing"
    if source is not None: assign_drape_target(target, source, target_type)
    return target


def assign_drape_target(target, source, target_type: Optional[str]=None):
    if source is None: raise ValueError("drape target source is required")
    kind=str(target_type or getattr(target,"TargetType","FreeCAD Geometry"))
    if kind not in DrapeTargetSpec.VALID_TYPES: raise ValueError("unsupported drape target type")
    deflection=float(getattr(target,"CollisionDeflection",1.0)); thickness=float(getattr(target,"CollisionThickness",0.0))
    surface=collision_surface(source,deflection,thickness)
    target.TargetType=kind; target.SourceObject=source; target.SourceSignature=repr(source_signature(source,deflection,thickness))
    target.CollisionVertexCount=len(surface.vertices); target.CollisionTriangleCount=len(surface.triangles)
    status=target_status(target)
    target.TargetStatus=status["state"]; target.InvalidationReason=status["reason"]
    return target


# Install the recompute guard when the target contract is imported. This keeps
# saved/reloaded documents safe even when the Simulation workbench has not yet
# been selected in the GUI.
try:
    from freecad_cloth.simulation.SimulationStaleGuard import install as _install_simulation_guard
    _install_simulation_guard()
except (ImportError, AttributeError, TypeError):
    pass

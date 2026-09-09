"""Target-neutral draping/collision contract."""
from dataclasses import dataclass
import hashlib
import json
from typing import Optional, Tuple
from freecad_cloth.avatar.AvatarCollision import CollisionSurface, surface_from_freecad


@dataclass(frozen=True)
class DrapeTargetSpec:
    target_type: str
    source_name: str
    deflection: float = 1.0
    thickness: float = 0.0

    VALID_TYPES = ("Mannequin", "FreeCAD Geometry")

    def validate(self):
        if self.target_type not in self.VALID_TYPES:
            raise ValueError("unsupported drape target type")
        if not self.source_name.strip():
            raise ValueError("drape target source must not be empty")
        if self.deflection <= 0:
            raise ValueError("drape target deflection must be positive")
        if self.thickness < 0:
            raise ValueError("drape target thickness must not be negative")


def collision_surface(target, deflection=1.0, thickness=0.0) -> CollisionSurface:
    return surface_from_freecad(target, float(deflection), float(thickness))


def _digest_surface(vertices, triangles):
    """Return a deterministic digest of the complete collision topology."""
    payload = {
        "vertices": [tuple(round(float(c), 6) for c in vertex) for vertex in vertices],
        "triangles": [tuple(int(i) for i in triangle) for triangle in triangles],
    }
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _mesh_signature(target):
    if str(getattr(target, "AvatarType", "")) == "ClothAvatar":
        return (
            "ClothAvatar",
            str(getattr(target, "AvatarMeshProvider", "")),
            str(getattr(target, "AvatarMeshSource", "")),
            str(getattr(target, "AvatarMeshLicense", "")),
            int(getattr(target, "AvatarRevision", 0)),
            int(getattr(target, "MeshVertexCount", 0)),
            int(getattr(target, "MeshTriangleCount", 0)),
        )
    mesh = getattr(target, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return None
    try:
        vertices, triangles = topology
        return ("Mesh", len(vertices), len(triangles), _digest_surface(vertices, triangles))
    except (TypeError, ValueError, AttributeError):
        return None


def _geometry_signature(target):
    mesh_signature = _mesh_signature(target)
    if mesh_signature is not None:
        return mesh_signature
    shape = getattr(target, "Shape", None)
    if shape is not None:
        tessellate = getattr(shape, "tessellate", None)
        if callable(tessellate):
            try:
                if not shape.isNull():
                    vertices, faces = tessellate(1.0)
                    return ("Shape", _digest_surface(vertices, faces))
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass
        hash_code = getattr(shape, "hashCode", None)
        if callable(hash_code):
            try:
                return ("ShapeHash", int(hash_code()))
            except (TypeError, ValueError):
                pass
    return ("Unknown",)


def source_signature(target, deflection=1.0, thickness=0.0) -> Tuple:
    placement = getattr(target, "Placement", None)
    base = getattr(placement, "Base", None) if placement is not None else None
    rotation = getattr(placement, "Rotation", None) if placement is not None else None
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        str(getattr(target, "Name", "")),
        _geometry_signature(target),
        round(float(getattr(base, "x", 0.0)), 6),
        round(float(getattr(base, "y", 0.0)), 6),
        round(float(getattr(base, "z", 0.0)), 6),
        round(float(getattr(rotation, "Angle", 0.0)), 6) if rotation is not None else 0.0,
        round(float(getattr(axis, "x", 0.0)), 6) if axis is not None else 0.0,
        round(float(getattr(axis, "y", 0.0)), 6) if axis is not None else 0.0,
        round(float(getattr(axis, "z", 1.0)), 6) if axis is not None else 1.0,
        float(deflection), float(thickness),
    )


def target_status(target):
    """Return a deterministic user-facing state for a persistent DrapeTarget."""
    if target is None:
        return {"state": "missing", "message": "No drape target selected", "stale": True, "reason": "target missing"}
    if not bool(getattr(target, "Enabled", True)):
        return {"state": "disabled", "message": "Drape target is disabled", "stale": False, "reason": "target disabled"}
    target_type = str(getattr(target, "TargetType", ""))
    source = getattr(target, "SourceObject", None)
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        return {"state": "invalid", "message": "Unsupported drape target type", "stale": True, "reason": "unsupported target type"}
    if source is None:
        message = "Mannequin target has no source object" if target_type == "Mannequin" else "FreeCAD Geometry target has no source object"
        return {"state": "unassigned", "message": message, "stale": True, "reason": "source missing"}
    vertices = int(getattr(target, "CollisionVertexCount", 0))
    triangles = int(getattr(target, "CollisionTriangleCount", 0))
    if not getattr(target, "SourceSignature", "") or vertices <= 0 or triangles <= 0:
        return {"state": "unbuilt", "message": "Drape target collision surface needs to be built", "stale": True, "reason": "collision cache missing"}
    if target_type == "Mannequin" and str(getattr(source, "AvatarType", "")) == "ClothAvatar":
        return {"state": "ready", "message": "Managed humanoid drape target is ready", "stale": False, "reason": "managed avatar collision is rebuilt from authored mesh"}
    try:
        current = repr(source_signature(source, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0))))
    except (AttributeError, TypeError, ValueError) as exc:
        return {"state": "invalid", "message": "Cannot inspect drape target: %s" % exc, "stale": True, "reason": "signature failed"}
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
    return {"state": "ready", "message": "Drape target collision surface is current", "stale": False, "reason": ""}


def refresh_drape_target(target):
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target source is required")
    return assign_drape_target(target, source, getattr(target, "TargetType", "FreeCAD Geometry"))


def create_drape_target(doc, source=None, target_type="FreeCAD Geometry", deflection=1.0, thickness=0.0):
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
    return target


def assign_drape_target(target, source, target_type: Optional[str] = None):
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


try:
    from freecad_cloth.simulation.SimulationStaleGuard import install as _install_simulation_guard
    _install_simulation_guard()
except (ImportError, AttributeError, TypeError):
    pass

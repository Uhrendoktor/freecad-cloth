"""Target-neutral draping/collision contract."""
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


def _mesh_signature(target):
    if str(getattr(target, "AvatarType", "")) == "ClothAvatar":
        return (
            "ClothAvatar",
            str(getattr(target, "AvatarMeshProvider", "")),
            str(getattr(target, "AvatarMeshSource", "")),
            str(getattr(target, "AvatarStatus", "")),
            int(getattr(target, "MeshVertexCount", 0)),
            int(getattr(target, "MeshTriangleCount", 0)),
            str(getattr(target, "ParametersJSON", "")),
        )
    mesh = getattr(target, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return None
    try:
        vertices, triangles = topology
        if not vertices or not triangles:
            return ("Mesh", len(vertices), len(triangles), ())
        xs = [float(v.x) for v in vertices]
        ys = [float(v.y) for v in vertices]
        zs = [float(v.z) for v in vertices]
        descriptor = (
            len(vertices), len(triangles),
            tuple(round(value, 6) for value in (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))),
            tuple(round(sum(values), 6) for values in (xs, ys, zs)),
            tuple(round(sum(value * value for value in values), 6) for values in (xs, ys, zs)),
        )
        return ("Mesh",) + descriptor
    except (TypeError, ValueError, AttributeError):
        return None


def _geometry_signature(target):
    mesh_signature = _mesh_signature(target)
    if mesh_signature is not None:
        return mesh_signature
    shape = getattr(target, "Shape", None)
    if shape is not None:
        hash_code = getattr(shape, "hashCode", None)
        if callable(hash_code):
            try:
                return ("ShapeHash", int(hash_code()))
            except (TypeError, ValueError):
                pass
        tessellate = getattr(shape, "tessellate", None)
        if callable(tessellate):
            try:
                if not shape.isNull():
                    box = shape.BoundBox
                    return (
                        "Shape",
                        int(len(getattr(shape, "Solids", ()))),
                        int(len(getattr(shape, "Faces", ()))),
                        int(len(getattr(shape, "Edges", ()))),
                        int(len(getattr(shape, "Vertexes", ()))),
                        round(float(shape.Volume), 6),
                        round(float(shape.Area), 6),
                        round(float(box.XMin), 6), round(float(box.XMax), 6),
                        round(float(box.YMin), 6), round(float(box.YMax), 6),
                        round(float(box.ZMin), 6), round(float(box.ZMax), 6),
                    )
            except (AttributeError, TypeError, ValueError):
                pass
    return ("Unknown",)


def source_signature(target, deflection=1.0, thickness=0.0) -> Tuple:
    if str(getattr(target, "AvatarType", "")) == "ClothAvatar":
        return (
            str(getattr(target, "Name", "")),
            _geometry_signature(target),
            float(deflection),
            float(thickness),
        )
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
    source = getattr(target, "SourceObject", None)
    target_type = str(getattr(target, "TargetType", "FreeCAD Geometry"))
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        return {"state": "invalid", "message": "Unsupported drape target type", "stale": True, "reason": "unsupported target type"}
    if source is None:
        message = "Mannequin target has no source object" if target_type == "Mannequin" else "FreeCAD Geometry target has no source object"
        return {"state": "unassigned", "message": message, "stale": True, "reason": "source missing"}
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
        managed_avatar = (
            target_type == "Mannequin"
            and str(getattr(source, "AvatarType", "")) == "ClothAvatar"
            and str(getattr(source, "AvatarMeshProvider", "")) == "makehuman-hm08"
            and str(getattr(source, "AvatarStatus", "")) == "Valid"
        )
        if managed_avatar:
            return {"state": "ready", "message": "Drape target collision surface is current", "stale": False, "reason": "managed MakeHuman avatar owns mesh rebuild state"}
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

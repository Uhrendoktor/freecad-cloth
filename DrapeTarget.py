"""Persistent lifecycle and dependency authority for drape collision targets."""
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
        if self.target_type not in self.VALID_TYPES:
            raise ValueError("unsupported drape target type")
        if not self.source_name.strip():
            raise ValueError("drape target source must not be empty")
        if self.deflection <= 0:
            raise ValueError("drape target deflection must be positive")
        if self.thickness < 0:
            raise ValueError("drape target thickness must not be negative")


STATES = ("VALID", "STALE", "INVALID", "REFRESHING", "READY_FOR_SIMULATION")
DEPENDENCY_CLASSES = ("pattern geometry", "sewing topology", "avatar", "arrangement", "collision parameters", "source placement")


def collision_surface(target, deflection=1.0, thickness=0.0) -> CollisionSurface:
    return surface_from_freecad(target, float(deflection), float(thickness))


def _geometry_signature(target):
    if target is None:
        return ("missing",)
    shape = getattr(target, "Shape", None)
    if shape is not None:
        try:
            if not shape.isNull():
                return ("Shape", int(shape.hashCode()))
        except (AttributeError, TypeError, ValueError):
            pass
    mesh = getattr(target, "Mesh", None)
    if mesh is not None:
        topology = getattr(mesh, "Topology", None)
        if topology is not None:
            try:
                vertices, triangles = topology
                return ("Mesh", len(vertices), len(triangles))
            except (TypeError, ValueError):
                pass
    return ("Unknown",)


def _placement_signature(target):
    placement = getattr(target, "Placement", None)
    if placement is None:
        return ()
    base = getattr(placement, "Base", None)
    rotation = getattr(placement, "Rotation", None)
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)),
        float(getattr(rotation, "Angle", 0.0)) if rotation is not None else 0.0,
        float(getattr(axis, "x", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "y", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "z", 1.0)) if axis is not None else 1.0,
    )


def source_signature(target, deflection=1.0, thickness=0.0) -> Tuple:
    return (
        str(getattr(target, "Name", "")), str(getattr(target, "Label", "")),
        _geometry_signature(target), _placement_signature(target),
        float(deflection), float(thickness),
    )


def _object_signature(obj):
    """Stable persisted-input signature; never depends on Python object identity."""
    if obj is None:
        return ("missing",)
    props = []
    for name in sorted(str(p) for p in getattr(obj, "PropertiesList", ())):
        if name in {"SourceSignature", "DependencySignature", "PatternSignature", "SewingSignature", "AvatarSignature", "ArrangementSignature", "TargetStatus", "LifecycleState", "InvalidationReason"}:
            continue
        try:
            value = getattr(obj, name)
        except (AttributeError, RuntimeError):
            continue
        if name == "Shape":
            value = _geometry_signature(obj)
        elif name == "Placement":
            value = _placement_signature(obj)
        else:
            try:
                value = repr(value)
            except Exception:
                value = str(value)
        props.append((name, value))
    return (str(getattr(obj, "Name", "")), str(getattr(obj, "Label", "")), tuple(props))


def _links(target, property_name):
    value = getattr(target, property_name, ())
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(value)
    return (value,)


def dependency_signatures(target):
    source = getattr(target, "SourceObject", None)
    values = {
        "pattern geometry": tuple(sorted((_object_signature(o) for o in _links(target, "PatternDependencies")), key=repr)),
        "sewing topology": tuple(sorted((_object_signature(o) for o in _links(target, "SewingDependencies")), key=repr)),
        "avatar": tuple(sorted((_object_signature(o) for o in _links(target, "AvatarDependencies")), key=repr)),
        "arrangement": tuple(sorted((_object_signature(o) for o in _links(target, "ArrangementDependencies")), key=repr)),
        "collision parameters": (float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0))),
        "source placement": (str(getattr(source, "Name", "")), _geometry_signature(source), _placement_signature(source)),
    }
    return values


def _dependency_digest(values):
    return hashlib.sha256(repr(tuple((k, values[k]) for k in DEPENDENCY_CLASSES)).encode("utf-8")).hexdigest()


def _changed_reasons(target, current):
    reasons = []
    old = {name: str(getattr(target, name, "")) for name in ("PatternSignature", "SewingSignature", "AvatarSignature", "ArrangementSignature", "CollisionParametersSignature", "SourcePlacementSignature")}
    mapping = {
        "pattern geometry": ("PatternSignature", current["pattern geometry"]),
        "sewing topology": ("SewingSignature", current["sewing topology"]),
        "avatar": ("AvatarSignature", current["avatar"]),
        "arrangement": ("ArrangementSignature", current["arrangement"]),
        "collision parameters": ("CollisionParametersSignature", current["collision parameters"]),
        "source placement": ("SourcePlacementSignature", current["source placement"]),
    }
    for reason, (prop, value) in mapping.items():
        if old[prop] and old[prop] != repr(value):
            reasons.append(reason)
    return reasons


def _status(target, state, message, reason=""):
    return {"state": state, "message": message, "stale": state in ("STALE", "INVALID", "REFRESHING"), "reason": reason}


def target_status(target):
    """Read the persisted lifecycle and verify it against authored dependencies."""
    if target is None:
        return _status(None, "INVALID", "No drape target selected", "target missing")
    state = str(getattr(target, "LifecycleState", ""))
    if state not in STATES:
        state = "INVALID"
    if not bool(getattr(target, "Enabled", True)):
        return _status(target, "INVALID", "Drape target is disabled", "target disabled")
    target_type = str(getattr(target, "TargetType", "FreeCAD Geometry"))
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        return _status(target, "INVALID", "Unsupported drape target type", "unsupported target type")
    source = getattr(target, "SourceObject", None)
    if source is None:
        return _status(target, "INVALID", "Drape target has no source object", "source missing")
    try:
        current = dependency_signatures(target)
        reasons = _changed_reasons(target, current)
        digest = _dependency_digest(current)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        return _status(target, "INVALID", "Cannot inspect drape target: %s" % exc, "dependency inspection failed")
    vertices = int(getattr(target, "CollisionVertexCount", 0))
    triangles = int(getattr(target, "CollisionTriangleCount", 0))
    if not getattr(target, "DependencySignature", "") or vertices <= 0 or triangles <= 0:
        return _status(target, "STALE", "Drape target collision surface needs to be refreshed", "collision cache missing")
    if digest != str(getattr(target, "DependencySignature", "")):
        reason = ", ".join(reasons) if reasons else "dependency changed"
        return _status(target, "STALE", "Drape target is stale; refresh before simulation", reason)
    if state == "REFRESHING":
        return _status(target, "REFRESHING", "Drape target is refreshing", str(getattr(target, "InvalidationReason", "")))
    if state == "VALID":
        return _status(target, "READY_FOR_SIMULATION", "Drape target is current and ready for simulation")
    if state == "READY_FOR_SIMULATION":
        return _status(target, state, "Drape target is current and ready for simulation")
    return _status(target, state, str(getattr(target, "InvalidationReason", "Drape target requires refresh")), str(getattr(target, "InvalidationReason", "")))


def _set_signatures(target, current):
    target.DependencySignature = _dependency_digest(current)
    target.PatternSignature = repr(current["pattern geometry"])
    target.SewingSignature = repr(current["sewing topology"])
    target.AvatarSignature = repr(current["avatar"])
    target.ArrangementSignature = repr(current["arrangement"])
    target.CollisionParametersSignature = repr(current["collision parameters"])
    target.SourcePlacementSignature = repr(current["source placement"])
    target.SourceSignature = repr(source_signature(getattr(target, "SourceObject", None), getattr(target, "CollisionDeflection", 1.0), getattr(target, "CollisionThickness", 0.0)))


def refresh_drape_target(target):
    """Synchronously rebuild and persist a target, with REFRESHING as a durable guard."""
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target source is required")
    target.LifecycleState = "REFRESHING"
    target.TargetStatus = "REFRESHING"
    target.InvalidationReason = "explicit refresh"
    doc = getattr(target, "Document", None)
    if doc is not None:
        doc.recompute()
    surface = collision_surface(source, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0)))
    target.CollisionVertexCount = len(surface.vertices)
    target.CollisionTriangleCount = len(surface.triangles)
    _set_signatures(target, dependency_signatures(target))
    target.InvalidationReason = ""
    target.LifecycleState = "READY_FOR_SIMULATION"
    target.TargetStatus = "READY_FOR_SIMULATION"
    if doc is not None:
        doc.recompute()
    return target


def invalidate_drape_target(target, reason):
    """Persist invalidation immediately; reason is part of the document state."""
    if target is None:
        return None
    reason = str(reason).strip() or "dependency changed"
    target.LifecycleState = "STALE"
    target.TargetStatus = "STALE"
    target.InvalidationReason = reason
    return target


def set_drape_target_dependencies(target, pattern=None, sewing=None, avatar=None, arrangement=None):
    """Attach persistent dependency links used by the lifecycle authority."""
    for name, values in (("PatternDependencies", pattern), ("SewingDependencies", sewing), ("AvatarDependencies", avatar), ("ArrangementDependencies", arrangement)):
        if values is not None:
            setattr(target, name, tuple(values) if isinstance(values, (list, tuple)) else (values,))
    return target


class DrapeTargetProxy:
    def execute(self, target):
        try:
            current = dependency_signatures(target)
            reasons = _changed_reasons(target, current)
            digest = _dependency_digest(current)
            if getattr(target, "LifecycleState", "") == "REFRESHING":
                return
            if not getattr(target, "DependencySignature", ""):
                invalidate_drape_target(target, "collision cache missing")
            elif digest != str(getattr(target, "DependencySignature", "")):
                invalidate_drape_target(target, ", ".join(reasons) if reasons else "dependency changed")
            target.TargetStatus = str(getattr(target, "LifecycleState", "INVALID"))
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            invalidate_drape_target(target, "dependency inspection failed: %s" % exc)


def create_drape_target(doc, source=None, target_type="FreeCAD Geometry", deflection=1.0, thickness=0.0):
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        raise ValueError("unsupported drape target type")
    if deflection <= 0 or thickness < 0:
        raise ValueError("invalid collision tessellation or thickness")
    if source is None and target_type != "Mannequin":
        raise ValueError("a FreeCAD Geometry target requires a source object")
    target = doc.addObject("App::FeaturePython", "DrapeTarget")
    target.Label = "Drape Target"
    for prop, typ, group in (
        ("TargetType", "App::PropertyString", "Draping"), ("SourceObject", "App::PropertyLink", "Draping"),
        ("PatternDependencies", "App::PropertyLinkList", "Dependencies"), ("SewingDependencies", "App::PropertyLinkList", "Dependencies"),
        ("AvatarDependencies", "App::PropertyLinkList", "Dependencies"), ("ArrangementDependencies", "App::PropertyLinkList", "Dependencies"),
        ("CollisionDeflection", "App::PropertyFloat", "Collision"), ("CollisionThickness", "App::PropertyFloat", "Collision"),
        ("Enabled", "App::PropertyBool", "Draping"), ("CollisionVertexCount", "App::PropertyInteger", "State"),
        ("CollisionTriangleCount", "App::PropertyInteger", "State"), ("SourceSignature", "App::PropertyString", "State"),
        ("DependencySignature", "App::PropertyString", "State"), ("PatternSignature", "App::PropertyString", "State"),
        ("SewingSignature", "App::PropertyString", "State"), ("AvatarSignature", "App::PropertyString", "State"),
        ("ArrangementSignature", "App::PropertyString", "State"), ("CollisionParametersSignature", "App::PropertyString", "State"),
        ("SourcePlacementSignature", "App::PropertyString", "State"), ("LifecycleState", "App::PropertyEnumeration", "State"),
        ("TargetStatus", "App::PropertyString", "State"), ("InvalidationReason", "App::PropertyString", "State"),
    ):
        target.addProperty(typ, prop, group)
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
    target.Proxy = DrapeTargetProxy()
    if source is not None:
        target.SourceObject = source
        refresh_drape_target(target)
    return target


def assign_drape_target(target, source, target_type: Optional[str] = None):
    if source is None:
        raise ValueError("drape target source is required")
    kind = str(target_type or getattr(target, "TargetType", "FreeCAD Geometry"))
    if kind not in DrapeTargetSpec.VALID_TYPES:
        raise ValueError("unsupported drape target type")
    target.TargetType = kind
    target.SourceObject = source
    return refresh_drape_target(target)

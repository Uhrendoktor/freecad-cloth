# Copyright (C) 2026 FreeCAD Cloth contributors
"""Target-neutral draping/collision contract."""

from typing import ClassVar

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.shared.SourceSignature import source_signature

DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM = 5.0


@pydantic_dataclass(frozen=True)
class DrapeTargetSpec:
    """Public data model or service class for DrapeTargetSpec."""

    target_type: str
    source_name: str
    deflection: float = 1.0
    thickness: float = 0.0

    VALID_TYPES: ClassVar[tuple[str, str]] = ("Mannequin", "FreeCAD Geometry")

    def validate(self) -> None:
        """Validate target type and collision dimensions.

        Raises:
            ValueError: If the target type, source name, deflection, or thickness is invalid.
        """
        if self.target_type not in self.VALID_TYPES:
            msg = "unsupported drape target type"
            raise ValueError(msg)
        if not self.source_name.strip():
            msg = "drape target source must not be empty"
            raise ValueError(msg)
        if self.deflection <= 0:
            msg = "drape target deflection must be positive"
            raise ValueError(msg)
        if self.thickness < 0:
            msg = "drape target thickness must not be negative"
            raise ValueError(msg)


def collision_surface(
    target: object,
    deflection: float = 1.0,
    thickness: float = 0.0,
) -> CollisionSurface:
    """Build a validated collision surface from a FreeCAD source.

    Args:
        target: FreeCAD shape or mesh object used as the collision source.
        deflection: Positive tessellation deflection for shape-backed inputs.
        thickness: Non-negative collision thickness in model units.

    Returns:
        A validated, solver-neutral collision surface.

    Raises:
        TypeError: If target does not expose usable shape or mesh geometry.
        ValueError: If tessellation, topology, or collision dimensions are invalid.
    """
    return surface_from_freecad(target, float(deflection), float(thickness))


def target_status(target: object | None) -> dict[str, str | bool]:
    """Summarize whether the persisted collision cache is current.

    Args:
        target: Persistent DrapeTarget feature, or None when no target is assigned.

    Returns:
        A deterministic state, status message, stale flag, and invalidation reason.
    """
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


def refresh_drape_target(target: object) -> object:
    """Rebuild the persistent target's collision cache from its current source.

    Args:
        target: Persisted target whose source and collision settings are refreshed.

    Returns:
        The refreshed target feature.

    Raises:
        ValueError: If the target does not have an assigned source.
    """
    source = getattr(target, "SourceObject", None)
    if source is None:
        msg = "drape target source is required"
        raise ValueError(msg)
    return assign_drape_target(target, source, getattr(target, "TargetType", "FreeCAD Geometry"))


def create_drape_target(
    doc: object,
    source: object | None = None,
    target_type: str = "FreeCAD Geometry",
    deflection: float = 1.0,
    thickness: float = 0.0,
) -> object:
    """Create a persistent DrapeTarget feature and optionally assign its source.

    Args:
        doc: FreeCAD document that owns the persistent target.
        source: Optional collision source; geometry targets require one.
        target_type: Supported source representation, either Mannequin or FreeCAD Geometry.
        deflection: Positive tessellation deflection in model units.
        thickness: Non-negative collision thickness in model units.

    Returns:
        The created persistent DrapeTarget feature.

    Raises:
        ValueError: If the type, source, deflection, or collision thickness is invalid.
    """
    if target_type not in DrapeTargetSpec.VALID_TYPES:
        msg = "unsupported drape target type"
        raise ValueError(msg)
    if deflection <= 0 or thickness < 0:
        msg = "invalid collision tessellation or thickness"
        raise ValueError(msg)
    if source is None and target_type != "Mannequin":
        msg = "a FreeCAD Geometry target requires a source object"
        raise ValueError(msg)
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


def assign_drape_target(
    target: object,
    source: object | None,
    target_type: str | None = None,
) -> object:
    """Assign a source and refresh the persisted collision-cache metadata.

    Args:
        target: Existing persistent DrapeTarget feature being updated.
        source: FreeCAD source object used to build collision geometry.
        target_type: Optional target representation; the existing type is preserved by default.

    Returns:
        The updated persistent target feature.

    Raises:
        ValueError: If the source is absent or the target type is unsupported.
        TypeError: If the source does not expose usable collision geometry.
    """
    if source is None:
        msg = "drape target source is required"
        raise ValueError(msg)
    kind = str(target_type or getattr(target, "TargetType", "FreeCAD Geometry"))
    if kind not in DrapeTargetSpec.VALID_TYPES:
        msg = "unsupported drape target type"
        raise ValueError(msg)
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

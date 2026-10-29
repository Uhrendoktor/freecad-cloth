# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression coverage for the persistent DrapeTarget state contract."""

from types import SimpleNamespace

from freecad_cloth.simulation.DrapeTarget import source_signature, target_status
from tests.support.assertions import require

DEFLECTION_MM = 1.0
ZERO_THICKNESS_MM = 0.0
BUILT_VERTEX_COUNT = 8
BUILT_TRIANGLE_COUNT = 12
SHAPE_HASH_INITIAL = 1
SHAPE_HASH_CHANGED = 2
ALTERNATE_DEFLECTION_MM = 0.5
BODY_NAME = "Body"
TARGET_TYPE = "FreeCAD Geometry"
EXPECTED_MISSING_CACHE_STATUS = {
    "state": "unbuilt",
    "message": "Drape target collision surface needs to be built",
    "stale": True,
    "reason": "collision cache missing",
}


def _shape(value: int) -> SimpleNamespace:
    """Build a shape fixture with a replaceable content hash.

    Args:
        value: Synthetic native shape hash.

    Returns:
        A shape-like object consumed by the source signature implementation.
    """
    shape = SimpleNamespace(value=value)

    def is_null() -> bool:
        """Report that the synthetic source shape is not null."""
        return False

    def hash_code() -> int:
        """Return the current synthetic source hash."""
        return shape.value

    shape.isNull = is_null
    shape.hashCode = hash_code
    return shape


def _target(source: object, **overrides: object) -> SimpleNamespace:
    """Build a current target record with optional persisted-property overrides.

    Args:
        source: Geometry used to initialize the source signature.
        overrides: Target fields that replace the normal current-cache values.

    Returns:
        A SimpleNamespace representing the persistent target feature.
    """
    values: dict[str, object] = {
        "Enabled": True,
        "TargetType": TARGET_TYPE,
        "SourceObject": source,
        "CollisionDeflection": DEFLECTION_MM,
        "CollisionThickness": ZERO_THICKNESS_MM,
        "SourceSignature": repr(source_signature(source, DEFLECTION_MM, ZERO_THICKNESS_MM)),
        "CollisionVertexCount": BUILT_VERTEX_COUNT,
        "CollisionTriangleCount": BUILT_TRIANGLE_COUNT,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_target_status_requires_a_built_collision_cache() -> None:
    """Report an unbuilt state when collision-cache metadata is missing."""
    source = SimpleNamespace(Name=BODY_NAME, Label=BODY_NAME, Shape=_shape(SHAPE_HASH_INITIAL))
    target = _target(
        source,
        SourceSignature="",
        CollisionVertexCount=0,
        CollisionTriangleCount=0,
    )
    require(
        condition=target_status(target) == EXPECTED_MISSING_CACHE_STATUS,
        message="A target with missing cache data must report the explicit unbuilt state.",
    )


def test_target_status_detects_geometry_change_without_silent_retargeting() -> None:
    """Report stale source geometry rather than treating changed content as current."""
    source = SimpleNamespace(Name=BODY_NAME, Label=BODY_NAME, Shape=_shape(SHAPE_HASH_INITIAL))
    target = _target(source)
    require(
        condition=target_status(target)["state"] == "ready",
        message="An unchanged target signature must be ready.",
    )

    source.__dict__["Shape"] = _shape(SHAPE_HASH_CHANGED)
    status = target_status(target)
    require(
        condition=status["state"] == "stale",
        message="Changed source geometry must mark the collision target stale.",
    )
    require(
        condition=status["stale"] is True,
        message="A target with changed geometry must be marked stale.",
    )
    require(
        condition="rebuild collision surface" in str(status["message"]),
        message="The stale message must explain that the collision surface needs rebuilding.",
    )
    require(
        condition="source" in str(status["reason"]),
        message="The stale reason must identify source changes.",
    )


def test_target_status_reports_disabled_without_calling_it_stale() -> None:
    """Keep disabled-target status separate from stale-cache status."""
    source = SimpleNamespace(Name=BODY_NAME, Label=BODY_NAME, Shape=_shape(SHAPE_HASH_INITIAL))
    target = _target(source, Enabled=False)
    status = target_status(target)
    require(
        condition=status["state"] == "disabled",
        message="A disabled target must report the disabled state.",
    )
    require(
        condition=status["stale"] is False,
        message="A disabled but otherwise current target must not be marked stale.",
    )
    require(
        condition=status["reason"] == "target disabled",
        message="A disabled target must report its disabled reason.",
    )


def test_target_status_detects_collision_parameter_change() -> None:
    """Detect changed collision tessellation settings against the persisted signature."""
    source = SimpleNamespace(Name=BODY_NAME, Label=BODY_NAME, Shape=_shape(SHAPE_HASH_INITIAL))
    target = _target(source)
    target.CollisionDeflection = ALTERNATE_DEFLECTION_MM
    status = target_status(target)
    require(
        condition=status["state"] == "stale",
        message="A changed deflection must invalidate the source signature.",
    )
    require(
        condition=status["stale"] is True,
        message="A target with changed collision settings must be marked stale.",
    )
    require(
        condition="tessellation" in str(status["reason"]),
        message="The stale reason must mention changed tessellation settings.",
    )

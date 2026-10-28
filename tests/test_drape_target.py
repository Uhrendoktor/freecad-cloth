# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for target-neutral drape identity and persistence state."""

from types import SimpleNamespace

import pytest

from freecad_cloth.simulation.DrapeTarget import DrapeTargetSpec, source_signature, target_status
from tests.support.assertions import require

DEFLECTION_MM = 1.0
THICKNESS_MM = 2.0
ALTERNATE_DEFLECTION_MM = 0.5
ALTERNATE_THICKNESS_MM = 4.0
MOVED_X_MM = 10.0
MOVED_Y_MM = -5.0
MOVED_ROTATION_DEGREES = 15.0
CHANGED_SHAPE_HASH = 2
INITIAL_SHAPE_HASH = 1
FIXED_BREP_HASH = 7
MESH_VERTEX_COUNT = 3
MESH_TRIANGLE_COUNT = 1
EXPECTED_TARGET_VERTEX_COUNT = 8
EXPECTED_TARGET_TRIANGLE_COUNT = 12
EXPECTED_DEFAULT_DEFLECTION_MM = 0.5
EXPECTED_DEFAULT_THICKNESS_MM = 1.5
INVALID_TARGET_NAME = "Unknown"
GEOMETRY_TARGET_TYPE = "FreeCAD Geometry"
MANNEQUIN_TARGET_TYPE = "Mannequin"
TARGET_NAME = "Chair"
TARGET_LABEL = "Chair target"
MESH_TARGET_NAME = "MeshTarget"
MESH_TARGET_LABEL = "Mesh target"


def _set_runtime_attribute(target: object, name: str, value: object) -> None:
    """Update a host-style dynamic attribute without narrowing its test fixture type.

    Args:
        target: Runtime fixture receiving an attribute update.
        name: Exact host API attribute name.
        value: Replacement runtime value.
    """
    setattr(target, name, value)


def _vector(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> SimpleNamespace:
    """Build a FreeCAD-vector stand-in.

    Args:
        x: Horizontal coordinate.
        y: Depth coordinate.
        z: Vertical coordinate.

    Returns:
        A vector-like object with x, y, and z attributes.
    """
    return SimpleNamespace(x=x, y=y, z=z)


def _placement(
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    angle: float = 0.0,
) -> SimpleNamespace:
    """Build a FreeCAD-placement stand-in.

    Args:
        x: Base translation on the x axis.
        y: Base translation on the y axis.
        z: Base translation on the z axis.
        angle: Rotation angle used in the source signature.

    Returns:
        A placement-like object with Base and Rotation properties.
    """
    rotation = SimpleNamespace(Angle=angle, Axis=_vector(z=1.0))
    return SimpleNamespace(Base=_vector(x, y, z), Rotation=rotation)


def _bound_box() -> SimpleNamespace:
    """Return deterministic shape bounds for signature fixtures."""
    return SimpleNamespace(
        XMin=0.0,
        XMax=1.0,
        YMin=0.0,
        YMax=1.0,
        ZMin=0.0,
        ZMax=1.0,
    )


def _shape(value: int) -> SimpleNamespace:
    """Build a shape-like object whose content hash can be changed in tests.

    Args:
        value: Current synthetic shape hash.

    Returns:
        A host-shaped object exposing the methods consumed by SourceSignature.
    """
    shape = SimpleNamespace(value=value, BoundBox=_bound_box())
    shape.isNull = lambda: False
    shape.hashCode = lambda: shape.value
    return shape


def _brep_shape(payload: str) -> SimpleNamespace:
    """Build a shape fixture that exposes deterministic BRep serialization.

    Args:
        payload: Serialized shape content used as the BRep signature input.

    Returns:
        A shape-like object with a stable hash and variable serialized content.
    """
    shape = SimpleNamespace(payload=payload, BoundBox=_bound_box())
    shape.isNull = lambda: False
    shape.hashCode = lambda: FIXED_BREP_HASH
    shape.exportBrepToString = lambda: shape.payload
    return shape


def _target() -> SimpleNamespace:
    """Build a basic named shape target for source-signature tests."""
    return SimpleNamespace(
        Name=TARGET_NAME,
        Label=TARGET_LABEL,
        Placement=_placement(),
        Shape=_shape(INITIAL_SHAPE_HASH),
    )


def _mesh_target(
    vertices: tuple[SimpleNamespace, ...],
    triangles: tuple[tuple[int, int, int], ...],
) -> SimpleNamespace:
    """Build a mesh target whose topology can be replaced during a test.

    Args:
        vertices: Ordered mesh vertices.
        triangles: Ordered triangle connectivity.

    Returns:
        A document-object stand-in exposing a replaceable Mesh.Topology tuple.
    """
    mesh = SimpleNamespace(Topology=(vertices, triangles))
    return SimpleNamespace(
        Name=MESH_TARGET_NAME,
        Label=MESH_TARGET_LABEL,
        Placement=_placement(),
        Mesh=mesh,
    )


def _persistent_target(source: object | None = None) -> SimpleNamespace:
    """Build a persisted-target stand-in with an up-to-date collision signature.

    Args:
        source: Source geometry used for the signature; a basic target is used by default.

    Returns:
        A target fixture with non-empty collision-cache metadata.
    """
    source_object = _target() if source is None else source
    return SimpleNamespace(
        TargetType=GEOMETRY_TARGET_TYPE,
        Enabled=True,
        CollisionDeflection=DEFLECTION_MM,
        CollisionThickness=THICKNESS_MM,
        SourceObject=source_object,
        CollisionVertexCount=EXPECTED_TARGET_VERTEX_COUNT,
        CollisionTriangleCount=EXPECTED_TARGET_TRIANGLE_COUNT,
        SourceSignature=repr(source_signature(source_object, DEFLECTION_MM, THICKNESS_MM)),
    )


def test_target_spec_accepts_supported_types() -> None:
    """Accept mannequin and FreeCAD geometry target specifications."""
    DrapeTargetSpec(MANNEQUIN_TARGET_TYPE, "ClothAvatar", DEFLECTION_MM, THICKNESS_MM).validate()
    DrapeTargetSpec(
        GEOMETRY_TARGET_TYPE,
        TARGET_NAME,
        EXPECTED_DEFAULT_DEFLECTION_MM,
        EXPECTED_DEFAULT_THICKNESS_MM,
    ).validate()


def test_target_spec_rejects_invalid_settings() -> None:
    """Reject unsupported source types, empty names, and invalid collision dimensions."""
    specs = (
        DrapeTargetSpec(INVALID_TARGET_NAME, TARGET_NAME),
        DrapeTargetSpec(GEOMETRY_TARGET_TYPE, ""),
        DrapeTargetSpec(GEOMETRY_TARGET_TYPE, TARGET_NAME, 0.0),
        DrapeTargetSpec(GEOMETRY_TARGET_TYPE, TARGET_NAME, DEFLECTION_MM, -1.0),
    )
    for spec in specs:
        with pytest.raises(ValueError):
            spec.validate()


def test_source_signature_tracks_geometry_placement_and_collision_settings() -> None:
    """Track geometry, placement, tessellation, and collision-thickness changes."""
    target = _target()
    baseline = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    _set_runtime_attribute(target.Shape, "value", CHANGED_SHAPE_HASH)
    require(
        condition=source_signature(target, DEFLECTION_MM, THICKNESS_MM) != baseline,
        message="A shape-content change must invalidate the source signature.",
    )
    _set_runtime_attribute(
        target,
        "Placement",
        _placement(MOVED_X_MM, MOVED_Y_MM, 0.0, MOVED_ROTATION_DEGREES),
    )
    moved = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    require(
        condition=moved != baseline,
        message="A placement change must invalidate the source signature.",
    )
    require(
        condition=source_signature(target, ALTERNATE_DEFLECTION_MM, THICKNESS_MM) != moved,
        message="A tessellation-deflection change must invalidate the source signature.",
    )
    require(
        condition=source_signature(target, ALTERNATE_DEFLECTION_MM, ALTERNATE_THICKNESS_MM)
        != source_signature(target, ALTERNATE_DEFLECTION_MM, THICKNESS_MM),
        message="A collision-thickness change must invalidate the source signature.",
    )


def test_shape_signature_hashes_geometry_content_when_counts_and_hash_are_unchanged() -> None:
    """Use serialized BRep content when its stable metadata stays unchanged."""
    target = _target()
    _set_runtime_attribute(target, "Shape", _brep_shape("brep-a"))
    baseline = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    _set_runtime_attribute(target, "Shape", _brep_shape("brep-b"))
    changed = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    require(
        condition=changed != baseline,
        message="Different serialized BRep content must change the source signature.",
    )


def test_mesh_signature_hashes_complete_topology_not_aggregate_counts() -> None:
    """Detect changed mesh coordinates even when vertex and face counts match."""
    vertices = (_vector(), _vector(x=1.0), _vector(y=1.0))
    target = _mesh_target(vertices, ((0, 1, 2),))
    baseline = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    changed_vertices = (_vector(), _vector(x=1.0), _vector(z=1.0))
    _set_runtime_attribute(target.Mesh, "Topology", (changed_vertices, ((0, 1, 2),)))
    require(
        condition=source_signature(target, DEFLECTION_MM, THICKNESS_MM) != baseline,
        message="Mesh coordinate changes must be represented in the source signature.",
    )


def test_mesh_signature_tracks_triangle_connectivity() -> None:
    """Detect connectivity changes when the ordered vertex list remains stable."""
    vertices = (_vector(), _vector(x=1.0), _vector(y=1.0))
    target = _mesh_target(vertices, ((0, 1, 2),))
    baseline = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    _set_runtime_attribute(target.Mesh, "Topology", (vertices, ((0, 2, 1),)))
    require(
        condition=source_signature(target, DEFLECTION_MM, THICKNESS_MM) != baseline,
        message="Triangle connectivity and winding must be represented in the signature.",
    )


def test_mesh_signature_tracks_triangle_order() -> None:
    """Detect face-order changes in a mesh with unchanged vertex and triangle counts."""
    vertices = (_vector(), _vector(x=1.0), _vector(y=1.0), _vector(z=1.0))
    triangles = ((0, 1, 2), (0, 2, 3))
    target = _mesh_target(vertices, triangles)
    baseline = source_signature(target, DEFLECTION_MM, THICKNESS_MM)
    _set_runtime_attribute(target.Mesh, "Topology", (vertices, (triangles[1], triangles[0])))
    require(
        condition=source_signature(target, DEFLECTION_MM, THICKNESS_MM) != baseline,
        message="Triangle order must be represented in the source signature.",
    )


def test_source_signature_is_stable() -> None:
    """Produce an identical signature for unchanged geometry and settings."""
    target = _target()
    require(
        condition=source_signature(target, DEFLECTION_MM, THICKNESS_MM)
        == source_signature(target, DEFLECTION_MM, THICKNESS_MM),
        message="The same source state must produce a deterministic signature.",
    )


def test_target_status_is_ready_when_signature_is_current() -> None:
    """Report a built target as ready while its source signature is current."""
    status = target_status(_persistent_target())
    require(
        condition=status["state"] == "ready",
        message="A target with a current collision cache must be ready.",
    )
    require(
        condition=status["stale"] is False,
        message="A current collision cache must not be marked stale.",
    )


def test_target_status_reports_source_change_as_stale() -> None:
    """Mark a target stale when the source geometry changes after building."""
    target = _persistent_target()
    _set_runtime_attribute(target.SourceObject.Shape, "value", 99)
    status = target_status(target)
    require(
        condition=status["state"] == "stale",
        message="A source-content change must invalidate the persisted signature.",
    )
    require(
        condition=status["stale"] is True,
        message="A changed source must be marked stale.",
    )
    require(
        condition="source" in str(status["reason"]),
        message="The stale reason must identify source invalidation.",
    )


def test_target_status_reports_missing_collision_cache() -> None:
    """Mark a target unbuilt when its collision-cache counts are absent."""
    target = _persistent_target()
    _set_runtime_attribute(target, "CollisionVertexCount", 0)
    status = target_status(target)
    require(
        condition=status["state"] == "unbuilt",
        message="A target without cached collision vertices must be unbuilt.",
    )
    require(
        condition=status["stale"] is True,
        message="A target with a missing collision cache must be marked stale.",
    )

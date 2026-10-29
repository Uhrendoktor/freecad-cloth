# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-facing body measurement, avatar fitting, and arrangement commands."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from importlib import import_module
from typing import Protocol, SupportsFloat, SupportsInt, cast

from freecad_cloth.shared.CommandIds import FITTING_COMMANDS

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
MeshTopology = tuple[tuple[Point3, ...], tuple[Triangle, ...]]


class _FittingSceneFeature(Protocol):
    """Persistent FreeCAD feature fields owned by the canonical fitting-scene schema."""

    Name: str
    Label: str
    Document: "_FittingDocument"
    FittingType: str
    MeasurementData: str
    MeasurementUnit: str
    PatternPieces: list[object]
    PiecePlacements: list[str]
    HomePlacements: list[str]
    ArrangementPoints: list[str]
    ArrangementAnchorData: list[str]
    BoundingVolumes: list[str]
    ArrangementPointObjects: list[str]
    BoundingVolumeObjects: list[str]
    SymmetryEnabled: bool
    FitStatus: str
    AvatarProxy: object | None
    Proxy: object


def _drape_target_source(doc: _FittingDocument | None) -> object | None:
    """Return the source object linked by the document's persistent drape target.

    Args:
        doc: Document that owns the target object, or None when no document exists.

    Returns:
        The assigned source object, or None while the target is unassigned.
    """
    if doc is None:
        return None
    return getattr(doc.getObject("DrapeTarget"), "SourceObject", None)


def _scene(doc: _FittingDocument | None) -> _FittingSceneFeature | None:
    """Find the fitting-scene feature stored in a document.

    Args:
        doc: Document to search, or None when no active document is available.

    Returns:
        The fitting-scene object, or None when the document has no scene.
    """
    if doc is None:
        return None
    selected = next(
        (obj for obj in doc.Objects if getattr(obj, "FittingType", "") == "FittingScene"),
        None,
    )
    return cast("_FittingSceneFeature | None", selected)


def _safe_name(value: object) -> str:
    """Convert an arbitrary label to a stable FreeCAD object-name fragment.

    Args:
        value: Label or identifier to normalize.

    Returns:
        An alphanumeric/underscore string, using "Item" when the input is empty.
    """
    return "".join(character if character.isalnum() else "_" for character in str(value)) or "Item"


def _ensure_anchor_property(scene: object) -> None:
    """Ensure a fitting scene exposes its persistent surface-anchor property.

    Args:
        scene: Fitting-scene object that may need the property added.
    """
    if hasattr(scene, "ArrangementAnchorData"):
        return
    add_property = getattr(scene, "addProperty", None)
    if callable(add_property):
        add_property("App::PropertyStringList", "ArrangementAnchorData", "Arrangement")
        setattr(scene, "ArrangementAnchorData", [])


def _anchor_records(scene: object) -> dict[str, dict[str, object]]:
    """Decode persistent anchor records indexed by arrangement-point name.

    Args:
        scene: Fitting-scene object holding serialized anchor records.

    Returns:
        Valid JSON-object records keyed by their nonempty arrangement-point names.
    """
    _ensure_anchor_property(scene)
    result: dict[str, dict[str, object]] = {}
    for value in tuple(getattr(scene, "ArrangementAnchorData", ()) or ()):
        try:
            decoded: object = json.loads(str(value))
            if not isinstance(decoded, dict):
                continue
            name = str(decoded.get("name", ""))
            if name:
                result[name] = cast("dict[str, object]", decoded)
        except (AttributeError, TypeError, ValueError):
            continue
    return result


def _store_anchor_records(
    scene: object,
    records: Mapping[str, Mapping[str, object]],
) -> None:
    """Persist anchor references in a stable key-sorted JSON representation.

    Args:
        scene: Fitting-scene object receiving the serialized records.
        records: Anchor records indexed by arrangement-point name.
    """
    _ensure_anchor_property(scene)
    setattr(
        scene,
        "ArrangementAnchorData",
        [
            json.dumps(dict(records[name]), sort_keys=True, separators=(",", ":"))
            for name in sorted(records)
        ],
    )


def _point_xyz(point: object) -> Point3:
    """Normalize a tuple-like coordinate or FreeCAD vector to an XYZ triple.

    Args:
        point: Three-dimensional coordinate sequence or vector-like object.

    Returns:
        The first three coordinates converted to floats.
    """
    try:
        values = cast("Sequence[SupportsFloat | str | bytes]", point)
        return cast("Point3", tuple(float(value) for value in values[:3]))
    except (TypeError, ValueError, IndexError):
        return (
            float(getattr(point, "x")),
            float(getattr(point, "y")),
            float(getattr(point, "z")),
        )


def _geometry_round(value: float, digits: int = 5) -> float:
    """Round a geometry scalar and canonicalize signed zero for stable signatures.

    Args:
        value: Geometry value to round.
        digits: Number of decimal places retained.

    Returns:
        The rounded scalar, with both positive and negative zero represented as 0.0.
    """
    rounded = round(float(value), digits)
    return 0.0 if not rounded else rounded


def _points_in_local_space(
    points: tuple[Point3, ...],
    placement: object,
    vector_factory: Callable[..., object] | None,
) -> tuple[Point3, ...]:
    """Undo an object's placement for points read from a placed mesh.

    Args:
        points: Mesh vertex coordinates reported by FreeCAD.
        placement: Object placement providing inverse and vector transformation APIs.
        vector_factory: Optional vector constructor used by tests.

    Returns:
        The mesh vertices in object-local coordinates.

    Raises:
        ImportError: If no FreeCAD host module is loaded and no vector factory is injected.
    """
    make_vector = vector_factory
    if make_vector is None:
        host_module = sys.modules.get("FreeCAD")
        if host_module is None:
            msg = "FreeCAD must be loaded when converting placed mesh coordinates"
            raise ImportError(msg)
        make_vector = cast("Callable[..., object]", getattr(host_module, "Vector"))
    inverse = cast("Callable[[], object]", getattr(placement, "inverse"))()
    transform = cast("Callable[[object], object]", getattr(inverse, "multVec"))
    return tuple(_point_xyz(transform(make_vector(*point))) for point in points)


def _validated_mesh_topology(
    points: tuple[Point3, ...],
    faces: tuple[tuple[int, ...], ...],
) -> MeshTopology:
    """Validate mesh topology and narrow each face to a triangle.

    Args:
        points: Object-local mesh vertices.
        faces: Candidate integer-indexed face records.

    Returns:
        Nonempty vertices and triangular faces with in-range indices.

    Raises:
        ValueError: If vertices or faces are empty or a face is not a valid triangle.
    """
    if (
        not points
        or not faces
        or any(len(face) != 3 or min(face) < 0 or max(face) >= len(points) for face in faces)
    ):
        msg = "mesh topology must contain valid triangles"
        raise ValueError(msg)
    return points, cast("tuple[Triangle, ...]", faces)


def _mesh_topology_from_parts(
    target: object,
    vertices: Sequence[object],
    triangles: Sequence[Sequence[object]],
    vector_factory: Callable[..., object] | None,
) -> MeshTopology:
    """Convert raw FreeCAD topology into validated object-local mesh arrays.

    Args:
        target: FreeCAD target whose placement may need to be inverted.
        vertices: Raw mesh vertex values returned by the native API.
        triangles: Raw face-index records returned by the native API.
        vector_factory: Optional vector constructor used by focused tests.

    Returns:
        Validated local-space vertices and triangle indices.

    Raises:
        ValueError: If the topology is malformed or placement normalization fails.
    """
    points = tuple(_point_xyz(point) for point in vertices)
    placement = getattr(target, "Placement", None)
    if placement is not None:
        try:
            points = _points_in_local_space(points, placement, vector_factory)
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as exc:
            msg = "could not normalize target mesh vertices to object-local coordinates"
            raise ValueError(msg) from exc
    faces = tuple(
        tuple(int(cast("SupportsInt | str | bytes", index)) for index in face)
        for face in triangles
    )
    return _validated_mesh_topology(points, faces)


def _mesh_topology(
    target: object,
    *,
    vector_factory: Callable[..., object] | None = None,
) -> MeshTopology | None:
    """Return validated object-local vertices and triangle indices for a mesh target.

    Args:
        target: FreeCAD target object whose Mesh.Topology may be available.
        vector_factory: Optional FreeCAD-compatible vector factory used by tests.

    Returns:
        Local-space vertices and triangles, or None when the target is not a mesh.

    Raises:
        ValueError: If the target exposes malformed mesh topology or its placement
            cannot be inverted to object-local coordinates.
    """
    mesh = getattr(target, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return None
    try:
        vertices, triangles = cast("tuple[Sequence[object], Sequence[Sequence[object]]]", topology)
        return _mesh_topology_from_parts(target, vertices, triangles, vector_factory)
    except (TypeError, ValueError, AttributeError) as exc:
        msg = "the selected target has unusable mesh topology"
        raise ValueError(msg) from exc


def _mesh_target_signature(
    target: object,
    vertices: tuple[Point3, ...],
    triangles: tuple[Triangle, ...],
) -> str:
    """Sign mesh topology and provider identity without mutable vertex positions.

    Args:
        target: Mesh-bearing FreeCAD object.
        vertices: Validated object-local vertex coordinates.
        triangles: Validated triangular face indices.

    Returns:
        A stable digest reflecting mesh connectivity or avatar provider identity.
    """
    if str(getattr(target, "AvatarType", "")) == "ClothAvatar":
        provider_source = getattr(target, "ProviderSource", None)
        source_signature = (
            _target_signature(provider_source)
            if provider_source is not None and provider_source is not target
            else None
        )
        payload = json.dumps(
            {
                "avatar_type": "ClothAvatar",
                "provider_id": str(getattr(target, "AvatarProviderId", "")),
                "mesh_provider": str(getattr(target, "AvatarMeshProvider", "")),
                "mesh_source": str(getattr(target, "AvatarMeshSource", "")),
                "triangle_count": len(triangles),
                "declared_triangle_count": int(
                    getattr(target, "MeshTriangleCount", len(triangles))
                ),
                "provider_source_signature": source_signature,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return "avatar-mesh-topology:" + hashlib.sha256(payload).hexdigest()
    payload = json.dumps(
        {"vertex_count": len(vertices), "triangles": triangles},
        separators=(",", ":"),
    ).encode("ascii")
    return "mesh-topology:" + hashlib.sha256(payload).hexdigest()


def _normalized_shape_copy(target: object, shape: object) -> object:
    """Copy a BRep and remove object placement before geometry is signed.

    Args:
        target: FreeCAD object whose placement may be applied to its shape.
        shape: Native shape copied and normalized to object-local coordinates.

    Returns:
        A normalized non-null shape copy.

    Raises:
        ValueError: If the copy cannot be normalized or the resulting shape is null.
    """
    try:
        normalized = cast("Callable[[], object]", getattr(shape, "copy"))()
        placement = getattr(target, "Placement", None)
        if placement is not None:
            inverse = cast("Callable[[], object]", getattr(placement, "inverse"))()
            matrix = cast("Callable[[], object]", getattr(inverse, "toMatrix"))()
            cast("Callable[[object], object]", getattr(normalized, "transformShape"))(matrix)
        if bool(cast("Callable[[], object]", getattr(normalized, "isNull"))()):
            msg = "the selected target shape is null"
            raise ValueError(msg)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        msg = "could not normalize the selected target shape"
        raise ValueError(msg) from exc
    return normalized


def _rounded_point(point: object) -> Point3:
    """Round a point to the geometry-signature precision.

    Args:
        point: FreeCAD point or three-coordinate sequence.

    Returns:
        The point's coordinates rounded to the stable signature precision.
    """
    return cast("Point3", tuple(_geometry_round(value) for value in _point_xyz(point)))


def _shape_signature_components(
    shape: object,
) -> tuple[
    tuple[Point3, ...],
    tuple[tuple[float, Point3], ...],
    tuple[tuple[str, float, Point3, int], ...],
    tuple[object, ...],
]:
    """Compute sorted vertex, edge, face, and bounding-box signature components.

    Args:
        shape: Normalized native FreeCAD shape.

    Returns:
        Sorted geometry components and the combined local-shape signature tuple.
    """
    vertices = tuple(
        sorted(
            _rounded_point(getattr(vertex, "Point"))
            for vertex in cast("Sequence[object]", getattr(shape, "Vertexes"))
        )
    )
    edges = tuple(
        sorted(
            (
                _geometry_round(float(getattr(edge, "Length"))),
                _rounded_point(getattr(edge, "CenterOfMass")),
            )
            for edge in cast("Sequence[object]", getattr(shape, "Edges"))
        )
    )
    faces = tuple(
        sorted(
            (
                type(getattr(face, "Surface")).__name__,
                _geometry_round(float(getattr(face, "Area"))),
                _rounded_point(getattr(face, "CenterOfMass")),
                len(tuple(cast("Sequence[object]", getattr(face, "Edges")))),
            )
            for face in cast("Sequence[object]", getattr(shape, "Faces"))
        )
    )
    box = getattr(shape, "BoundBox")
    signature = (
        "ShapeLocal",
        len(tuple(cast("Sequence[object]", getattr(shape, "Solids")))),
        len(vertices),
        vertices,
        edges,
        faces,
        _geometry_round(float(getattr(box, "XMin"))),
        _geometry_round(float(getattr(box, "XMax"))),
        _geometry_round(float(getattr(box, "YMin"))),
        _geometry_round(float(getattr(box, "YMax"))),
        _geometry_round(float(getattr(box, "ZMin"))),
        _geometry_round(float(getattr(box, "ZMax"))),
    )
    return vertices, edges, faces, signature


def _shape_geometry_signature(target: object, shape: object) -> str:
    """Create a local-geometry signature for a supported non-mesh target.

    Args:
        target: FreeCAD object owning the source shape.
        shape: Native shape to copy and inspect.

    Returns:
        A deterministic representation of the shape's local geometry.

    Raises:
        ValueError: If the shape is unusable or exposes no supported geometry.
    """
    normalized = _normalized_shape_copy(target, shape)
    try:
        vertices, edges, faces, signature = _shape_signature_components(normalized)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        msg = "could not normalize the selected target shape"
        raise ValueError(msg) from exc
    if not vertices and not edges and not faces:
        msg = "the selected target does not expose supported geometry"
        raise ValueError(msg)
    return repr(("shape-geometry", signature))


def _target_signature(target: object) -> str:
    """Sign local geometry/topology, deliberately excluding object placement and vertices.

    Mesh anchors use stable triangle connectivity plus barycentric coordinates. This lets a
    generated avatar deform its vertices during skeleton posing without invalidating the
    anchor, while still detecting a topology rebuild. Non-mesh anchors follow object
    placement and become stale if the underlying shape geometry itself changes.

    Args:
        target: FreeCAD object whose local geometry should be signed.

    Returns:
        A stable mesh-topology digest or non-mesh geometry signature.

    Raises:
        ValueError: If the target does not expose supported geometry or its mesh/shape
            data cannot be normalized.
    """
    mesh_topology = _mesh_topology(target)
    if mesh_topology is not None:
        vertices, triangles = mesh_topology
        return _mesh_target_signature(target, vertices, triangles)
    shape = getattr(target, "Shape", None)
    if shape is None:
        msg = "the selected target does not expose supported geometry"
        raise ValueError(msg)
    return _shape_geometry_signature(target, shape)


def _vector_subtract(left: Point3, right: Point3) -> Point3:
    """Subtract two three-dimensional vectors component-wise.

    Args:
        left: Vector from which the right operand is subtracted.
        right: Vector subtracted from the left operand.

    Returns:
        The component-wise difference.
    """
    return (
        left[0] - right[0],
        left[1] - right[1],
        left[2] - right[2],
    )


def _vector_dot(left: Point3, right: Point3) -> float:
    """Calculate the dot product of two three-dimensional vectors.

    Args:
        left: First vector operand.
        right: Second vector operand.

    Returns:
        The scalar dot product.
    """
    return sum(left[index] * right[index] for index in range(3))


def _triangle_dot_products(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> tuple[float, float, float, float, float, float]:
    """Calculate the six dot products used by triangle closest-point regions.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Dot products d1 through d6 in the order used by the region tests.
    """
    ab = _vector_subtract(b, a)
    ac = _vector_subtract(c, a)
    ap = _vector_subtract(point, a)
    bp = _vector_subtract(point, b)
    cp = _vector_subtract(point, c)
    return (
        _vector_dot(ab, ap),
        _vector_dot(ac, ap),
        _vector_dot(ab, bp),
        _vector_dot(ac, bp),
        _vector_dot(ab, cp),
        _vector_dot(ac, cp),
    )


def _triangle_ab_vertex_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3 | None:
    """Return vertex-region weights for triangle vertices A or B.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Weights for vertex A or B when the query falls in either vertex region,
        or None when another region is closer.
    """
    d1, d2, d3, d4, _, _ = _triangle_dot_products(point, a, b, c)
    if d1 <= 0.0 and d2 <= 0.0:
        return (1.0, 0.0, 0.0)
    if d3 >= 0.0 and d4 <= d3:
        return (0.0, 1.0, 0.0)
    return None


def _triangle_ab_edge_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3 | None:
    """Return barycentric weights when edge AB is the closest triangle region.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Edge-AB barycentric weights, or None when another region is closer.
    """
    d1, d2, d3, d4, _, _ = _triangle_dot_products(point, a, b, c)
    vc = d1 * d4 - d3 * d2
    if not (vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0):
        return None
    denom = d1 - d3
    v = d1 / denom if abs(denom) > 1e-15 else 0.0
    return (1.0 - v, v, 0.0)


def _triangle_c_vertex_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3 | None:
    """Return barycentric weights when vertex C is the closest region.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Weights for vertex C, or None when another region is closer.
    """
    _, _, _, _, d5, d6 = _triangle_dot_products(point, a, b, c)
    if d6 >= 0.0 and d5 <= d6:
        return (0.0, 0.0, 1.0)
    return None


def _triangle_ac_edge_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3 | None:
    """Return barycentric weights when edge AC is the closest triangle region.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Edge-AC barycentric weights, or None when another region is closer.
    """
    d1, d2, _, _, d5, d6 = _triangle_dot_products(point, a, b, c)
    vb = d5 * d2 - d1 * d6
    if not (vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0):
        return None
    denom = d2 - d6
    w = d2 / denom if abs(denom) > 1e-15 else 0.0
    return (1.0 - w, 0.0, w)


def _triangle_bc_edge_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3 | None:
    """Return barycentric weights when edge BC is the closest triangle region.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Edge-BC barycentric weights, or None when another region is closer.
    """
    _, _, d3, d4, d5, d6 = _triangle_dot_products(point, a, b, c)
    va = d3 * d6 - d5 * d4
    if not (va <= 0.0 and d4 - d3 >= 0.0 and d5 - d6 >= 0.0):
        return None
    denom = (d4 - d3) + (d5 - d6)
    w = (d4 - d3) / denom if abs(denom) > 1e-15 else 0.0
    return (0.0, 1.0 - w, w)


def _triangle_interior_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3:
    """Return barycentric weights for the triangle's interior closest region.

    Args:
        point: Query point.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Barycentric weights summing to one, with a stable fallback for degeneracy.
    """
    d1, d2, d3, d4, d5, d6 = _triangle_dot_products(point, a, b, c)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc
    if abs(denom) <= 1e-15:
        return (1.0, 0.0, 0.0)
    inverse = 1.0 / denom
    v, w = vb * inverse, vc * inverse
    return (1.0 - v - w, v, w)


def _closest_triangle_weights(
    point: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
) -> Point3:
    """Return barycentric coordinates of the closest point on triangle ABC.

    Args:
        point: Query point in the same coordinate system as the triangle.
        a: First triangle vertex.
        b: Second triangle vertex.
        c: Third triangle vertex.

    Returns:
        Barycentric coordinates for the closest point, or vertex A for a degenerate
        triangle whose interior denominator is effectively zero.
    """
    return (
        _triangle_ab_vertex_weights(point, a, b, c)
        or _triangle_ab_edge_weights(point, a, b, c)
        or _triangle_c_vertex_weights(point, a, b, c)
        or _triangle_ac_edge_weights(point, a, b, c)
        or _triangle_bc_edge_weights(point, a, b, c)
        or _triangle_interior_weights(point, a, b, c)
    )


def _weighted_triangle_point(vertices, triangle, weights):
    """Interpolate the current mesh position associated with saved triangle weights."""
    return tuple(
        sum(vertices[triangle[i]][axis] * float(weights[i]) for i in range(3)) for axis in range(3)
    )


def _mesh_anchor_local_position(
    target, anchor, *, vector_factory: Callable[..., object] | None = None
):
    """Resolve a mesh anchor against current vertices, preserving its material location."""
    topology = _mesh_topology(target, vector_factory=vector_factory)
    if topology is None or "triangle_index" not in anchor or "barycentric" not in anchor:
        return tuple(float(value) for value in anchor.get("local_point", (0.0, 0.0, 0.0)))
    vertices, triangles = topology
    triangle_index = int(anchor["triangle_index"])
    if triangle_index < 0 or triangle_index >= len(triangles):
        msg = "anchored mesh triangle no longer exists"
        raise ValueError(msg)
    weights = tuple(float(value) for value in anchor["barycentric"])
    if len(weights) != 3 or abs(sum(weights) - 1.0) > 1e-5:
        msg = "stored mesh-anchor barycentric coordinates are invalid"
        raise ValueError(msg)
    return _weighted_triangle_point(vertices, triangles[triangle_index], weights)


def _mesh_anchor_coordinates(
    target, local_point, *, vector_factory: Callable[..., object] | None = None
):
    """Find the closest mesh triangle and retain its barycentric hit coordinate."""
    topology = _mesh_topology(target, vector_factory=vector_factory)
    if topology is None:
        return None
    vertices, triangles = topology
    best = None
    best_distance = float("inf")
    for triangle_index, triangle in enumerate(triangles):
        a, b, c = (vertices[index] for index in triangle)
        weights = _closest_triangle_weights(local_point, a, b, c)
        projected = _weighted_triangle_point(vertices, triangle, weights)
        distance = sum((projected[axis] - local_point[axis]) ** 2 for axis in range(3))
        if distance < best_distance:
            best_distance = distance
            best = (triangle_index, weights, projected)
    if best is None:
        msg = "the selected mesh contains no usable surface triangles"
        raise ValueError(msg)
    return best


def _anchor_record_status(scene, target, anchor, document=None):
    if target is None:
        return "missing target"
    if document is None:
        document = getattr(scene, "Document", None) if scene is not None else None
    if document is not None:
        configured_target = _drape_target_source(document)
        if configured_target is None:
            return "unconfigured target"
        if str(getattr(configured_target, "Name", "")) != str(getattr(target, "Name", "")):
            return "wrong target"
    try:
        return (
            "valid"
            if _target_signature(target) == str(anchor.get("geometry_signature", ""))
            else "stale"
        )
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return "invalid"


def _anchor_world_position(target, anchor):
    """Resolve a persistent local/mesh anchor into the document's world coordinates."""
    import FreeCAD as App

    local = _mesh_anchor_local_position(target, anchor)
    placement = getattr(target, "Placement", None)
    if placement is not None:
        world = placement.multVec(App.Vector(*local))
        return float(world.x), float(world.y), float(world.z)
    return tuple(float(value) for value in local)


def _refresh_anchor_positions(scene, update_visuals=False):
    """Follow valid anchors after a target deforms or its object Placement changes."""
    if scene is None or getattr(scene, "Document", None) is None:
        return ()
    import FreeCAD as App

    doc = scene.Document
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    anchors = _anchor_records(scene)
    values = {
        point.name: point
        for point in (
            ArrangementPoint.from_string(value)
            for value in tuple(getattr(scene, "ArrangementPoints", ()) or ())
        )
    }
    changed = []
    for name, anchor in anchors.items():
        point = values.get(name)
        if point is None:
            continue
        target = doc.getObject(str(anchor.get("target", "")))
        if _anchor_record_status(scene, target, anchor) != "valid":
            continue
        try:
            x, y, z = _anchor_world_position(target, anchor)
        except (AttributeError, IndexError, TypeError, ValueError, RuntimeError):
            continue
        if max(abs(point.x - x), abs(point.y - y), abs(point.offset - z)) <= 1e-6:
            continue
        updated = ArrangementPoint(
            point.name, x, y, z, point.wrap_direction, point.rotation_z, point.symmetry_group
        )
        values[name] = updated
        changed.append((name, updated))
    if not changed:
        return ()

    scene.ArrangementPoints = [values[key].to_string() for key in sorted(values)]
    if update_visuals:
        import Part

        objects = {
            str(getattr(obj, "PointName", "")): obj
            for obj in (
                doc.getObject(str(name))
                for name in tuple(getattr(scene, "ArrangementPointObjects", ()) or ())
            )
            if obj is not None
        }
        for name, point in changed:
            obj = objects.get(name)
            if obj is None:
                continue
            obj.X, obj.Y, obj.Offset, obj.RotationZ = (
                point.x,
                point.y,
                point.offset,
                point.rotation_z,
            )
            center = App.Vector(point.x, point.y, point.offset)
            obj.Shape = Part.makeCompound(
                [
                    Part.makeSphere(0.8, center),
                    Part.makeCircle(7.0, center, App.Vector(0.0, 0.0, 1.0)),
                    Part.makeLine(
                        center - App.Vector(10.0, 0.0, 0.0),
                        center + App.Vector(10.0, 0.0, 0.0),
                    ),
                    Part.makeLine(
                        center - App.Vector(0.0, 10.0, 0.0),
                        center + App.Vector(0.0, 10.0, 0.0),
                    ),
                ]
            )
    return tuple(name for name, _point in changed)


def arrangement_anchor_status(point):
    """Report whether a snap point's persisted surface reference is still current."""
    expected = str(getattr(point, "AnchorGeometrySignature", "") or "")
    if not expected:
        return "unanchored"
    target = getattr(point, "AnchorTarget", None)
    if target is None:
        return "missing target"
    document = getattr(point, "Document", None)
    scene = _scene(document) if document is not None else None
    return _anchor_record_status(scene, target, {"geometry_signature": expected}, document=document)


_FITTING_MARKER_GROUP_NAME = "ClothFittingMarkers"
_FITTING_MARKER_GROUP_LABEL = "Fitting / Arrangement Markers (automatic)"


class _FittingMarkerGroup(Protocol):
    """Small structural interface for the FreeCAD presentation group."""

    TypeId: str
    Label: str
    Name: str
    Group: tuple[object, ...]

    def addObject(self, obj: object) -> None: ...


class _FittingDocument(Protocol):
    """Document API used to organize generated marker features."""

    Objects: Sequence[object]

    def getObject(self, name: str) -> object | None: ...

    def addObject(self, type_id: str, name: str) -> object: ...

    def removeObject(self, name: str) -> None: ...


def refresh_avatar_anchor_positions(document: object, avatar: object) -> tuple[str, ...]:
    """Refresh fitting anchors when the persistent drape target belongs to an avatar.

    Args:
        document: FreeCAD document containing the fitting scene and drape target.
        avatar: Avatar object whose mesh has just been rebuilt.

    Returns:
        Names of arrangement points whose persisted positions were refreshed.
    """
    typed_document = cast("_FittingDocument", document)
    scene = _scene(typed_document)
    target = typed_document.getObject("DrapeTarget")
    if scene is None or getattr(target, "SourceObject", None) is not avatar:
        return ()
    return tuple(_refresh_anchor_positions(scene, update_visuals=True))


def _fitting_marker_group(
    doc: _FittingDocument, create: bool = False
) -> _FittingMarkerGroup | None:
    """Return the presentation-only container for generated fitting display aids."""
    group = doc.getObject(_FITTING_MARKER_GROUP_NAME)
    if group is None and create:
        group = doc.addObject("App::DocumentObjectGroup", _FITTING_MARKER_GROUP_NAME)
    if group is not None:
        if str(getattr(group, "TypeId", "")) != "App::DocumentObjectGroup":
            msg = (
                f"reserved fitting marker name {_FITTING_MARKER_GROUP_NAME!r} "
                "is used by a non-group object"
            )
            raise RuntimeError(msg)
        group = cast("_FittingMarkerGroup", group)
        group.Label = _FITTING_MARKER_GROUP_LABEL
    return group


def _remove_stale_fitting_markers(doc: _FittingDocument, wanted_names: set[str]) -> None:
    """Remove obsolete generated marker features, never authored geometry."""
    for obj in tuple(doc.Objects or ()):
        name = str(getattr(obj, "Name", "") or "")
        role = str(getattr(obj, "FittingType", "") or "")
        is_arrangement_marker = role == "ArrangementPoint" and name.startswith("ArrangementPoint_")
        is_volume_marker = role == "BoundingVolume" and name.startswith("BoundingVolume_")
        if name and name not in wanted_names and (is_arrangement_marker or is_volume_marker):
            doc.removeObject(name)


def _sync_visuals(scene: _FittingSceneFeature) -> None:
    """Synchronize visible FreeCAD point/volume adapters from canonical fitting records.

    Args:
        scene: Persistent scene whose arrangement points and bounding volumes drive markers.
    """
    import FreeCAD as App
    import Part

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint, BoundingVolume

    _ensure_anchor_property(scene)
    _refresh_anchor_positions(scene)
    anchor_records = _anchor_records(scene)
    points = tuple(ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)
    volumes = tuple(BoundingVolume.from_string(v) for v in scene.BoundingVolumes)
    wanted_names = {"ArrangementPoint_" + _safe_name(point.name) for point in points}
    wanted_names.update("BoundingVolume_" + _safe_name(volume.name) for volume in volumes)
    _remove_stale_fitting_markers(scene.Document, wanted_names)
    point_objects = []
    volume_objects = []
    existing = {o.Name: o for o in scene.Document.Objects}
    for point in points:
        name = "ArrangementPoint_" + _safe_name(point.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Snap target: " + point.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty(
                "App::PropertyString", "FittingType", "Fitting"
            ).FittingType = "ArrangementPoint"
        for prop, value in (
            ("PointName", point.name),
            ("WrapDirection", point.wrap_direction),
            ("SymmetryGroup", point.symmetry_group),
        ):
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyString", prop, "Fitting")
            setattr(obj, prop, value)
        if not hasattr(obj, "X"):
            obj.addProperty("App::PropertyDistance", "X", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Y", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Offset", "Arrangement")
            obj.addProperty("App::PropertyAngle", "RotationZ", "Arrangement")
        if not hasattr(obj, "AnchorTarget"):
            obj.addProperty("App::PropertyLinkGlobal", "AnchorTarget", "Surface Anchor")
            obj.addProperty("App::PropertyString", "AnchorSubelement", "Surface Anchor")
            obj.addProperty("App::PropertyVector", "AnchorLocalPoint", "Surface Anchor")
            obj.addProperty("App::PropertyString", "AnchorGeometrySignature", "Surface Anchor")
            obj.addProperty("App::PropertyString", "AnchorStatus", "Surface Anchor")
        obj.X, obj.Y, obj.Offset, obj.RotationZ = point.x, point.y, point.offset, point.rotation_z
        anchor = anchor_records.get(point.name)
        if anchor:
            obj.AnchorTarget = scene.Document.getObject(str(anchor.get("target", "")))
            obj.AnchorSubelement = str(anchor.get("subelement", ""))
            obj.AnchorGeometrySignature = str(anchor.get("geometry_signature", ""))
            local_point = tuple(
                cast("Iterable[object]", anchor.get("local_point", (0.0, 0.0, 0.0)))
            )
            obj.AnchorLocalPoint = App.Vector(*(float(v) for v in local_point))
            obj.AnchorStatus = arrangement_anchor_status(obj)
        else:
            obj.AnchorTarget = None
            obj.AnchorSubelement = ""
            obj.AnchorGeometrySignature = ""
            obj.AnchorLocalPoint = App.Vector(0.0, 0.0, 0.0)
            obj.AnchorStatus = "unanchored"
        if obj.AnchorStatus in {
            "stale",
            "missing target",
            "invalid",
            "wrong target",
            "unconfigured target",
        }:
            obj.Label = "Stale anchor: " + point.name
            obj.ViewObject.ShapeColor = (0.95, 0.24, 0.16)
            obj.ViewObject.LineColor = (0.65, 0.10, 0.08)
        else:
            obj.Label = "Snap target: " + point.name
            obj.ViewObject.ShapeColor = (0.15, 0.75, 1.0)
            obj.ViewObject.LineColor = (0.05, 0.45, 0.72)
        center = App.Vector(point.x, point.y, point.offset)
        obj.Shape = Part.makeCompound(
            [
                Part.makeSphere(0.8, center),
                Part.makeCircle(7.0, center, App.Vector(0.0, 0.0, 1.0)),
                Part.makeLine(
                    center - App.Vector(10.0, 0.0, 0.0),
                    center + App.Vector(10.0, 0.0, 0.0),
                ),
                Part.makeLine(
                    center - App.Vector(0.0, 10.0, 0.0),
                    center + App.Vector(0.0, 10.0, 0.0),
                ),
            ]
        )
        obj.ViewObject.LineWidth = 2.0
        point_objects.append(obj)
    for volume in volumes:
        name = "BoundingVolume_" + _safe_name(volume.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Bounding Volume: " + volume.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty(
                "App::PropertyString", "FittingType", "Fitting"
            ).FittingType = "BoundingVolume"
        if not hasattr(obj, "VolumeName"):
            obj.addProperty("App::PropertyString", "VolumeName", "Fitting")
            obj.addProperty("App::PropertyVector", "Center", "Volume")
            obj.addProperty("App::PropertyVector", "Size", "Volume")
        obj.VolumeName = volume.name
        obj.Center = App.Vector(*volume.center)
        obj.Size = App.Vector(*volume.size)
        corner = App.Vector(
            volume.center[0] - volume.size[0] / 2.0,
            volume.center[1] - volume.size[1] / 2.0,
            volume.center[2] - volume.size[2] / 2.0,
        )
        obj.Shape = Part.makeBox(volume.size[0], volume.size[1], volume.size[2], corner)
        volume_objects.append(obj)
    scene.ArrangementPointObjects = [obj.Name for obj in point_objects]
    scene.BoundingVolumeObjects = [obj.Name for obj in volume_objects]
    marker_objects = point_objects + volume_objects
    group = _fitting_marker_group(scene.Document, create=bool(marker_objects))
    if group is not None:
        if marker_objects:
            children = {
                str(getattr(child, "Name", "") or "")
                for child in tuple(getattr(group, "Group", ()) or ())
            }
            for marker in marker_objects:
                marker_name = str(getattr(marker, "Name", "") or "")
                if marker_name not in children:
                    group.addObject(marker)
                    children.add(marker_name)
        elif not tuple(getattr(group, "Group", ()) or ()):
            scene.Document.removeObject(str(getattr(group, "Name", "")))
    for obj in marker_objects:
        obj.ViewObject.Visibility = True


def create_fitting_scene() -> _FittingSceneFeature:
    """Create the persistent fitting scene, or return its existing instance.

    Returns:
        Canonical fitting-scene feature stored in the active FreeCAD document.
    """
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene

    doc = cast("_FittingDocument", App.ActiveDocument or App.newDocument("ClothSewing"))
    existing_scene = _scene(doc)
    if existing_scene is not None:
        return existing_scene
    obj = cast("_FittingSceneFeature", doc.addObject("App::FeaturePython", "FittingScene"))
    obj.Label = "Avatar Fitting Scene"
    obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "FittingScene"
    obj.addProperty(
        "App::PropertyString", "MeasurementData", "Measurements"
    ).MeasurementData = BodyMeasurements().to_json()
    obj.addProperty("App::PropertyString", "MeasurementUnit", "Measurements").MeasurementUnit = "mm"
    obj.addProperty("App::PropertyLinkListGlobal", "PatternPieces", "Fitting")
    obj.addProperty("App::PropertyStringList", "PiecePlacements", "Fitting").PiecePlacements = []
    obj.addProperty("App::PropertyStringList", "HomePlacements", "Fitting").HomePlacements = []
    obj.addProperty(
        "App::PropertyStringList", "ArrangementPoints", "Arrangement"
    ).ArrangementPoints = []
    obj.addProperty(
        "App::PropertyStringList", "ArrangementAnchorData", "Arrangement"
    ).ArrangementAnchorData = []
    obj.addProperty(
        "App::PropertyStringList", "BoundingVolumes", "Arrangement"
    ).BoundingVolumes = []
    obj.addProperty(
        "App::PropertyStringList", "ArrangementPointObjects", "Arrangement"
    ).ArrangementPointObjects = []
    obj.addProperty(
        "App::PropertyStringList", "BoundingVolumeObjects", "Arrangement"
    ).BoundingVolumeObjects = []
    obj.addProperty("App::PropertyBool", "SymmetryEnabled", "Arrangement").SymmetryEnabled = True
    obj.addProperty("App::PropertyString", "FitStatus", "Fitting").FitStatus = "Unassigned"
    obj.Proxy = _FittingProxy()
    FittingScene().validate()
    doc.recompute()
    return obj


def set_body_measurements(
    measurements: Mapping[str, float],
    unit: str = "mm",
) -> _FittingSceneFeature:
    """Validate and persist the body's measured dimensions on the fitting scene.

    Args:
        measurements: Named positive measurements expressed in the selected unit.
        unit: Measurement unit restricted by the body-measurement schema.

    Returns:
        Updated fitting-scene feature after storing the canonical measurement JSON.

    Raises:
        ValueError: If the unit or any named measurement violates the schema.
    """
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements

    doc = cast("_FittingDocument", App.ActiveDocument or App.newDocument("ClothSewing"))
    scene = _scene(doc) or create_fitting_scene()
    data = BodyMeasurements(dict(measurements), unit)
    data.validate()
    scene.MeasurementData = data.to_json()
    scene.MeasurementUnit = data.unit
    scene.FitStatus = "Measurements set"
    doc.recompute()
    return scene


def assign_avatar_source(source: object | None = None) -> object:
    """Assign a selected body or mannequin as the fitting scene's avatar source.

    Args:
        source: Optional FreeCAD shape or mesh. When omitted, the current GUI
            selection is searched for a supported geometry object.

    Returns:
        The updated fitting scene.

    Raises:
        ValueError: If no supported source object is selected or supplied.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    from freecad_cloth.simulation.DrapeTarget import (
        DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM,
        assign_drape_target,
        create_drape_target,
    )

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if source is None:
        source = next(
            (
                obj
                for obj in Gui.Selection.getSelection()
                if hasattr(obj, "Shape") or hasattr(obj, "Mesh")
            ),
            None,
        )
    if source is None or not (hasattr(source, "Shape") or hasattr(source, "Mesh")):
        msg = "select a FreeCAD body or mesh to use as the avatar source"
        raise ValueError(msg)

    is_mannequin = str(getattr(source, "AvatarType", "")) == "ClothAvatar"
    target_type = "Mannequin" if is_mannequin else "FreeCAD Geometry"
    target_thickness = DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM if is_mannequin else 2.0
    target = doc.getObject("DrapeTarget")
    if target is None:
        create_drape_target(doc, source, target_type, 1.0, target_thickness)
    else:
        target.CollisionDeflection = 1.0
        target.CollisionThickness = target_thickness
        assign_drape_target(target, source, target_type)

    scene.AvatarProxy = source
    scene.FitStatus = "Avatar assigned"
    doc.recompute()
    return scene


def add_selected_pattern_pieces():
    import FreeCAD as App
    import FreeCADGui as Gui

    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene, PiecePlacement

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    pieces = [
        o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"
    ]
    if not pieces:
        msg = "select one or more pattern pieces before adding them to the fitting scene"
        raise ValueError(msg)
    existing = [PiecePlacement.from_string(v) for v in scene.PiecePlacements]
    homes = [PiecePlacement.from_string(v) for v in scene.HomePlacements]
    by_id = {p.piece_id: p for p in existing}
    home_by_id = {p.piece_id: p for p in homes}
    for piece in pieces:
        placement = piece.Placement
        base = placement.Base
        value = PiecePlacement(
            str(piece.PieceId),
            (float(base.x), float(base.y), float(base.z)),
            float(placement.Rotation.Angle),
        )
        by_id[value.piece_id] = value
        home_by_id.setdefault(value.piece_id, value)
    scene.PatternPieces = sorted(
        set(list(scene.PatternPieces) + pieces), key=lambda o: str(o.PieceId)
    )
    scene.PiecePlacements = [by_id[k].to_string() for k in sorted(by_id)]
    scene.HomePlacements = [home_by_id[k].to_string() for k in sorted(home_by_id)]
    avatar_source = _drape_target_source(doc)
    FittingScene(
        BodyMeasurements.from_json(scene.MeasurementData),
        getattr(avatar_source, "Label", "") if avatar_source else "",
        tuple(by_id.values()),
    ).validate()
    scene.FitStatus = "Ready" if avatar_source else "Pieces assigned"
    doc.recompute()
    return scene


def position_piece(piece, x, y, z=0.0, rotation_z=0.0):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if getattr(piece, "PatternType", "") != "PatternPiece":
        msg = "piece must be a Cloth PatternPiece object"
        raise ValueError(msg)
    placement = App.Placement(
        App.Vector(float(x), float(y), float(z)),
        App.Rotation(App.Vector(0, 0, 1), float(rotation_z)),
    )
    piece.Placement = placement
    entries = {
        p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)
    }
    entries[str(piece.PieceId)] = PiecePlacement(
        str(piece.PieceId), (float(x), float(y), float(z)), float(rotation_z)
    )
    scene.PiecePlacements = [entries[k].to_string() for k in sorted(entries)]
    doc.recompute()
    return piece


def create_arrangement_point(
    name, x, y, offset=0.0, wrap_direction="front", rotation_z=0.0, symmetry_group="", mirror=False
):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    point = ArrangementPoint(
        str(name),
        float(x),
        float(y),
        float(offset),
        str(wrap_direction),
        float(rotation_z),
        str(symmetry_group),
    )
    point.validate()
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    values[point.name] = point
    anchors = _anchor_records(scene)
    anchors.pop(point.name, None)
    if mirror:
        if not symmetry_group.strip():
            msg = "mirror arrangement points require a symmetry group"
            raise ValueError(msg)
        mirrored = point.mirrored()
        values[mirrored.name] = mirrored
        anchors.pop(mirrored.name, None)
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    _store_anchor_records(scene, anchors)
    scene.SymmetryEnabled = bool(scene.SymmetryEnabled)
    _sync_visuals(scene)
    return point


def set_arrangement_point(
    name, x=None, y=None, offset=None, wrap_direction=None, rotation_z=None, symmetry_group=None
):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        msg = f"unknown arrangement point: {name}"
        raise ValueError(msg)
    old = values[name]
    point = ArrangementPoint(
        old.name,
        old.x if x is None else float(x),
        old.y if y is None else float(y),
        old.offset if offset is None else float(offset),
        old.wrap_direction if wrap_direction is None else str(wrap_direction),
        old.rotation_z if rotation_z is None else float(rotation_z),
        old.symmetry_group if symmetry_group is None else str(symmetry_group),
    )
    point.validate()
    values[name] = point
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    anchors = _anchor_records(scene)
    anchors.pop(name, None)
    _store_anchor_records(scene, anchors)
    _sync_visuals(scene)
    doc.recompute()
    return point


def delete_arrangement_point(name):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before deleting an arrangement point"
        raise ValueError(msg)
    scene = _scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        msg = f"unknown arrangement point: {name}"
        raise ValueError(msg)
    del values[name]
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    anchors = _anchor_records(scene)
    anchors.pop(name, None)
    _store_anchor_records(scene, anchors)
    _sync_visuals(scene)
    return scene


def create_bounding_volume(name, center=(0.0, 0.0, 0.0), size=(100.0, 100.0, 100.0)):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BoundingVolume

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    volume = BoundingVolume(
        str(name), tuple(float(v) for v in center), tuple(float(v) for v in size)
    )
    volume.validate()
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    values[volume.name] = volume
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return volume


def delete_bounding_volume(name):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BoundingVolume

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before deleting a bounding volume"
        raise ValueError(msg)
    scene = _scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    if name not in values:
        msg = f"unknown bounding volume: {name}"
        raise ValueError(msg)
    del values[name]
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return scene


def set_symmetry_enabled(enabled=True):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before changing fitting symmetry"
        raise ValueError(msg)
    scene = _scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    scene.SymmetryEnabled = bool(enabled)
    doc.recompute()
    return scene


def apply_arrangement_point(piece, point, mirror=None):
    """Place a pattern piece at a named point, optionally using its symmetric mate."""
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    if getattr(piece, "PatternType", "") != "PatternPiece":
        msg = "piece must be a Cloth PatternPiece object"
        raise ValueError(msg)
    doc = App.ActiveDocument
    scene = _scene(doc) if doc else None
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if isinstance(point, str):
        if point not in values:
            msg = f"unknown arrangement point: {point}"
            raise ValueError(msg)
        point = values[point]
    point.validate()
    if mirror is True and scene.SymmetryEnabled:
        point = point.mirrored()
    rotations = {
        "front": point.rotation_z,
        "back": point.rotation_z + 180.0,
        "left": point.rotation_z + 90.0,
        "right": point.rotation_z - 90.0,
    }
    return position_piece(piece, point.x, point.y, point.offset, rotations[point.wrap_direction])


def reset_arrangement():
    """Restore every assigned piece to its saved pre-arrangement placement."""
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before resetting arrangement"
        raise ValueError(msg)
    scene = _scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    pieces = {str(p.PieceId): p for p in scene.PatternPieces}
    homes = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.HomePlacements)}
    current = {}
    for pid, placement in homes.items():
        piece = pieces.get(pid)
        if piece is None:
            continue
        x, y, z = placement.position
        piece.Placement = App.Placement(
            App.Vector(x, y, z), App.Rotation(App.Vector(0, 0, 1), placement.rotation_z)
        )
        current[pid] = placement
    scene.PiecePlacements = [current[k].to_string() for k in sorted(current)]
    scene.FitStatus = "Arrangement reset"
    doc.recompute()
    return scene


def create_simulation_from_fitting() -> object:
    """Create the canonical quality simulation from the current fitting scene.

    Returns:
        The quality-controlled simulation scene populated with the fitting
        scene's pattern pieces and assigned avatar source when one exists.

    Raises:
        ValueError: If there is no active document, no fitting scene, or no
            pattern piece assigned to that fitting scene.
    """
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before creating a simulation from fitting"
        raise ValueError(msg)
    scene = _scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    pieces = tuple(scene.PatternPieces)
    if not pieces:
        msg = "add at least one pattern piece to the fitting scene"
        raise ValueError(msg)

    from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene

    return create_quality_simulation_scene(
        doc,
        avatar_source=scene.AvatarProxy,
        cloth_pieces=pieces,
    )


def open_interactive_arrange(scene=None):
    """Open the direct-manipulation fitting panel for the active fitting scene."""
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before opening Interactive Arrange"
        raise RuntimeError(msg)
    scene = scene or _scene(doc) or create_fitting_scene()
    from freecad_cloth.avatar.FittingGui import show_fitting_task

    panel = show_fitting_task(scene)
    if Gui.activeDocument():
        Gui.activeDocument().activeView().fitAll()
    return panel


def create_arrangement_point_from_viewport():
    """Open Interactive Arrange and arm the viewport surface-pick workflow."""
    panel = open_interactive_arrange()
    panel.start_anchor_pick()
    return panel


def create_arrangement_anchor(
    name, target, world_point, subelement="Face", wrap_direction="front", rotation_z=0.0
):
    """Create a named snap point from a pick on persistent target geometry.

    The anchor keeps a target-local location. Mesh surfaces use triangle indices and
    barycentric weights so stable-topology deformations follow the same surface region;
    non-mesh surfaces follow their object's Placement. Incompatible geometry is marked
    stale instead of silently snapping to old world coordinates.
    """
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before creating a surface anchor"
        raise RuntimeError(msg)
    scene = _scene(doc) or create_fitting_scene()
    target_document = getattr(target, "Document", None) if target is not None else None
    if target_document is None or getattr(target_document, "Name", "") != doc.Name:
        msg = "select a surface on geometry in the active document"
        raise ValueError(msg)
    signature = _target_signature(target)
    try:
        coords = (float(world_point.x), float(world_point.y), float(world_point.z))
    except AttributeError:
        coords = tuple(float(value) for value in world_point[:3])
    if len(coords) != 3:
        msg = "picked surface location must contain three coordinates"
        raise ValueError(msg)
    world = App.Vector(*coords)
    try:
        local = target.Placement.inverse().multVec(world)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        local = world

    local_coords = (float(local.x), float(local.y), float(local.z))
    anchor = {
        "name": str(name),
        "target": str(target.Name),
        "subelement": str(subelement),
        "local_point": list(local_coords),
        "geometry_signature": signature,
    }
    mesh_hit = _mesh_anchor_coordinates(target, local_coords)
    if mesh_hit is not None:
        triangle_index, barycentric, projected = mesh_hit
        anchor["triangle_index"] = int(triangle_index)
        anchor["barycentric"] = [float(value) for value in barycentric]
        anchor["local_point"] = [float(value) for value in projected]
        local = App.Vector(*projected)
        try:
            world = target.Placement.multVec(local)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            world = local
        coords = (float(world.x), float(world.y), float(world.z))

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    point = ArrangementPoint(
        str(name), coords[0], coords[1], coords[2], str(wrap_direction), float(rotation_z)
    )
    point.validate()
    anchors = _anchor_records(scene)
    anchors[point.name] = anchor
    values = {
        item.name: item
        for item in (ArrangementPoint.from_string(value) for value in scene.ArrangementPoints)
    }
    values[point.name] = point
    scene.ArrangementPoints = [values[key].to_string() for key in sorted(values)]
    _store_anchor_records(scene, anchors)
    _sync_visuals(scene)
    doc.recompute()
    return point


class _FittingProxy:
    Type = "ClothFittingScene"

    def execute(self, obj):
        from freecad_cloth.avatar.AvatarFitting import (
            ArrangementPoint,
            BodyMeasurements,
            BoundingVolume,
            FittingScene,
            PiecePlacement,
        )

        measurements = BodyMeasurements.from_json(obj.MeasurementData)
        avatar_source = _drape_target_source(getattr(obj, "Document", None))
        avatar_name = getattr(avatar_source, "Label", "") if avatar_source else ""
        placements = tuple(PiecePlacement.from_string(v) for v in obj.PiecePlacements)
        points = tuple(ArrangementPoint.from_string(v) for v in obj.ArrangementPoints)
        volumes = tuple(BoundingVolume.from_string(v) for v in obj.BoundingVolumes)
        FittingScene(
            measurements, avatar_name, placements, points, volumes, bool(obj.SymmetryEnabled)
        ).validate()


COMMANDS = list(FITTING_COMMANDS)
_COMMAND_HANDLERS = {
    "ClothFitting_CreateScene": create_fitting_scene,
    "ClothFitting_InteractiveArrange": open_interactive_arrange,
    "ClothFitting_SetMeasurements": lambda: set_body_measurements(
        {"height": 1700, "chest": 900, "waist": 760, "hip": 960, "shoulder": 420}
    ),
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_AddPieces": add_selected_pattern_pieces,
    "ClothFitting_CreateArrangementPoint": create_arrangement_point_from_viewport,
    "ClothFitting_SetArrangementPoint": lambda: set_arrangement_point("Point1", x=0, y=0),
    "ClothFitting_DeleteArrangementPoint": lambda: delete_arrangement_point("Point1"),
    "ClothFitting_CreateBoundingVolume": lambda: create_bounding_volume("Volume1"),
    "ClothFitting_DeleteBoundingVolume": lambda: delete_bounding_volume("Volume1"),
    "ClothFitting_SetSymmetry": lambda: set_symmetry_enabled(True),
    "ClothFitting_ApplyArrangementPoint": lambda: _apply_selected_arrangement(),
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def _apply_selected_arrangement():
    import FreeCADGui as Gui

    scene = _scene(Gui.activeDocument().Document)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    piece = next(
        (
            o
            for o in Gui.Selection.getSelection()
            if getattr(o, "PatternType", "") == "PatternPiece"
        ),
        None,
    )
    point = next(
        (
            o
            for o in Gui.Selection.getSelection()
            if getattr(o, "FittingType", "") == "ArrangementPoint"
        ),
        None,
    )
    if piece is None or point is None:
        msg = "select a pattern piece and an arrangement point"
        raise ValueError(msg)
    return apply_arrangement_point(piece, point.PointName)


try:
    import FreeCADGui as Gui

    from freecad_cloth.common.CommandAdapter import register_commands

    register_commands(Gui, _COMMAND_HANDLERS)
except (ImportError, AttributeError):
    pass

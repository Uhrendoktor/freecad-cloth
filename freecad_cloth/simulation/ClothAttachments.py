"""Semantic avatar anchors backed by FreeCAD's native mesh queries.

This module maps named garment edges and avatar landmarks to solver particles.
Closest-facet and ray-intersection queries are delegated to FreeCAD's C++ Mesh API.
"""
from typing import Any

from dataclasses import dataclass
from math import isfinite, sqrt
from numbers import Integral


Point3 = tuple[float, float, float]


def _point(value: Any, label: Any) -> tuple[float, float, float]:
    try:
        result = tuple(float(component) for component in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("{} must be a finite 3D point".format(label)) from exc
    if len(result) != 3 or any(not isfinite(component) for component in result):
        raise ValueError("{} must be a finite 3D point".format(label))
    return result


def _indices(values: Any, label: Any) -> tuple[int, ...]:
    try:
        raw = tuple(values)
    except TypeError as exc:
        raise ValueError("{} must be an iterable of integer indices".format(label)) from exc
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in raw):
        raise ValueError("{} must contain only integer indices".format(label))
    return tuple(dict.fromkeys(int(value) for value in raw))


def _distance_squared(first: Any, second: Any) -> float:
    return sum((first[axis] - second[axis]) ** 2 for axis in range(3))


@dataclass(frozen=True)
class AttachmentProjection:
    """Auditable projection for one cloth particle."""

    particle_index: int
    source_position: Point3
    particle_position: Point3
    surface_point: Point3
    anchor_position: Point3
    outward_normal: Point3
    triangle_index: int
    source_distance_mm: float


@dataclass(frozen=True)
class ResolvedAttachmentTarget:
    """One semantic garment edge vertex tied to a named avatar landmark."""

    particle_index: int
    piece_id: str
    edge_id: str
    landmark_name: str
    target_position: Point3
    projection_direction: Point3


def select_attachment_particle_near_anchor(
    chain: Any, positions: Any, anchor: Any, max_distance_mm: Any=400.0, tie_tolerance_mm: Any=1e-6
) -> int:
    """Select the unique nearest vertex on a semantic boundary chain to a named landmark."""
    indices = _indices(chain, "attachment edge chain")
    points = tuple(_point(position, "particle position") for position in positions)
    target = _point(anchor, "avatar landmark")
    limit = float(max_distance_mm)
    tie_tolerance = float(tie_tolerance_mm)
    if not isfinite(limit) or limit <= 0.0:
        raise ValueError("attachment search distance must be positive and finite")
    if not isfinite(tie_tolerance) or tie_tolerance < 0.0:
        raise ValueError("attachment tie tolerance must be finite and non-negative")
    if not indices:
        raise ValueError("attachment edge chain is empty")
    if any(index < 0 or index >= len(points) for index in indices):
        raise ValueError("attachment edge references a particle outside the solver array")
    ranked = sorted((_distance_squared(points[index], target), index) for index in indices)
    best_distance_squared, best_index = ranked[0]
    if sqrt(best_distance_squared) > limit:
        raise ValueError("no particle on the semantic edge is near the avatar landmark")
    if (
        len(ranked) > 1
        and abs(sqrt(ranked[1][0]) - sqrt(best_distance_squared)) <= tie_tolerance
    ):
        raise ValueError("avatar landmark maps ambiguously to multiple edge vertices")
    return best_index


def project_avatar_attachments(
    positions: Any,
    particle_indices: Any,
    surface: Any,
    offset_mm: Any=3.0,
    max_distance_mm: Any=100.0,
    target_points: Any=None,
    projection_directions: Any=None,
) -> tuple[Any, Any]:
    """Project selected particles using FreeCAD's native Mesh ray/facet query.

    A semantic anchor may supply its intended front/back direction. Otherwise the
    adapter falls back to both radial directions. FreeCAD computes the ray/facet hit
    and the native facet normal supplies the offset direction.
    """
    try:
        import FreeCAD as App
        import Mesh
    except ImportError as exc:
        raise RuntimeError("avatar surface attachment requires FreeCAD's native Mesh API") from exc

    points = tuple(_point(position, "particle position") for position in positions)
    indices = _indices(particle_indices, "attachment particle selection")
    supplied_targets = {}
    for index, value in (target_points or {}).items():
        if isinstance(index, bool) or not isinstance(index, Integral):
            raise ValueError("avatar target-point keys must be integer particle indices")
        supplied_targets[int(index)] = _point(value, "avatar landmark projection point")
    if any(index not in indices for index in supplied_targets):
        raise ValueError("avatar target points must correspond to selected attachment particles")
    supplied_directions = {}
    for index, value in (projection_directions or {}).items():
        if isinstance(index, bool) or not isinstance(index, Integral):
            raise ValueError("avatar projection-direction keys must be integer particle indices")
        supplied_directions[int(index)] = _point(value, "avatar projection direction")
    if any(index not in indices for index in supplied_directions):
        raise ValueError("avatar projection directions must correspond to selected particles")
    if not indices:
        raise ValueError("Avatar Attachment mode requires at least one selected particle")
    if any(index < 0 or index >= len(points) for index in indices):
        raise ValueError("avatar attachment particle index is outside solver positions")

    offset = float(offset_mm)
    maximum_distance = float(max_distance_mm)
    if not isfinite(offset) or not 0.0 <= offset <= 100.0:
        raise ValueError("avatar attachment offset must be finite and between 0 and 100 mm")
    if not isfinite(maximum_distance) or maximum_distance <= 0.0:
        raise ValueError("maximum attachment distance must be positive and finite")

    try:
        surface.validate()
    except AttributeError as exc:
        raise ValueError("avatar attachment requires a validated DrapeTarget surface") from exc
    vertices = tuple(_point(vertex, "DrapeTarget vertex") for vertex in surface.vertices)
    raw_triangles = tuple(tuple(face) for face in surface.triangles)
    if not raw_triangles:
        raise ValueError("DrapeTarget surface has no triangles")
    if any(
        len(face) != 3
        or any(
            isinstance(index, bool)
            or not isinstance(index, Integral)
            or index < 0
            or index >= len(vertices)
            for index in face
        )
        for face in raw_triangles
    ):
        raise ValueError("DrapeTarget surface contains an invalid triangle")
    triangles = tuple(tuple(int(index) for index in face) for face in raw_triangles)

    native_mesh = Mesh.Mesh()
    native_mesh.addFacets(
        [(vertices[a], vertices[b], vertices[c]) for a, b, c in triangles]
    )
    native_facets = tuple(native_mesh.Facets)
    if not native_facets or not any(
        float(getattr(facet, "Area", 0.0)) > 1e-12 for facet in native_facets
    ):
        raise ValueError("DrapeTarget has no non-degenerate triangles")

    center_vector = App.Vector(*_point(surface.center, "DrapeTarget center"))
    updated = list(points)
    projections = []
    for particle_index in indices:
        particle_position = points[particle_index]
        source = supplied_targets.get(particle_index, particle_position)
        source_vector = App.Vector(*source)
        if particle_index in supplied_directions:
            outward_vector = App.Vector(*supplied_directions[particle_index])
            if float(outward_vector.Length) <= 1e-9:
                raise ValueError("avatar projection direction must be non-zero")
            outward_vector.normalize()
        else:
            outward_vector = source_vector - center_vector
            if float(outward_vector.Length) <= 1e-9:
                raise ValueError("avatar landmark at the DrapeTarget center has no projection direction")
            outward_vector.normalize()
        # Search both ways along the semantic axis. A landmark may sit just outside
        # the skin, where the outward ray can miss the local torso and hit a distant
        # arm instead. Keep the semantic outward vector separate from the ray used
        # to find the nearest surface so the attachment offset still points outward.
        preferred_direction = (
            float(outward_vector.x),
            float(outward_vector.y),
            float(outward_vector.z),
        )
        directions = (
            preferred_direction,
            tuple(-component for component in preferred_direction),
        )
        candidates = []
        for direction in directions:
            hits = native_mesh.nearestFacetOnRay(source, direction)
            for raw_triangle_index, hit_point in hits.items():
                if isinstance(raw_triangle_index, bool) or not isinstance(raw_triangle_index, Integral):
                    raise ValueError("FreeCAD Mesh returned a non-integer facet index")
                triangle_index = int(raw_triangle_index)
                if not 0 <= triangle_index < len(native_facets):
                    raise ValueError("FreeCAD Mesh returned a facet index outside its topology")
                hit = _point(hit_point, "FreeCAD Mesh ray intersection")
                distance = sqrt(_distance_squared(source, hit))
                candidates.append((distance, triangle_index, hit, direction))
        if not candidates:
            raise ValueError("FreeCAD Mesh found no ray/facet intersection for avatar landmark")
        source_distance, triangle_index, closest, hit_direction = min(
            candidates, key=lambda candidate: (candidate[0], candidate[1])
        )
        if source_distance > maximum_distance:
            raise ValueError(
                (
                    "avatar attachment is too far from the DrapeTarget surface: {:.2f} mm "
                    "(maximum {:.2f} mm; particle_index={}; source={}; particle={}; "
                    "direction={}; outward={}; hit={})"
                ).format(
                    source_distance,
                    maximum_distance,
                    particle_index,
                    tuple(round(value, 3) for value in source),
                    tuple(round(value, 3) for value in particle_position),
                    tuple(round(value, 3) for value in hit_direction),
                    preferred_direction,
                    tuple(round(value, 3) for value in closest),
                )
            )

        facet_normal = native_facets[triangle_index].Normal
        normal = App.Vector(float(facet_normal.x), float(facet_normal.y), float(facet_normal.z))
        if float(normal.Length) <= 1e-12:
            raise ValueError("FreeCAD returned a degenerate facet normal for an avatar anchor")
        normal.normalize()
        if float(normal.dot(outward_vector)) < 0.0:
            normal = -normal
        closest_vector = App.Vector(*closest)
        anchor_vector = closest_vector + normal * offset
        anchor_position = (float(anchor_vector.x), float(anchor_vector.y), float(anchor_vector.z))
        updated[particle_index] = anchor_position
        projections.append(
            AttachmentProjection(
                particle_index=particle_index,
                source_position=source,
                particle_position=particle_position,
                surface_point=closest,
                anchor_position=anchor_position,
                outward_normal=(float(normal.x), float(normal.y), float(normal.z)),
                triangle_index=triangle_index,
                source_distance_mm=source_distance,
            )
        )
    return tuple(updated), tuple(projections)


def resolve_avatar_attachment_targets(descriptors: Any, panel_data: Any, positions: Any, landmarks: Any) -> tuple[ResolvedAttachmentTarget, ...]:
    """Resolve stable descriptors into current vertices and authoritative target points."""
    points = tuple(_point(position, "particle position") for position in positions)
    records = tuple(str(value).strip() for value in (descriptors or ()) if str(value).strip())
    if not records:
        raise ValueError("Avatar Attachment mode requires semantic anchor descriptors")
    result = []
    seen_descriptors = set()
    used_vertices = set()
    for record in records:
        parts = record.split("|")
        if len(parts) != 3 or any(not part.strip() for part in parts):
            raise ValueError(
                "avatar anchor descriptor must be PieceId|SemanticEdgeId|landmark: {}".format(record)
            )
        piece_id, edge_id, landmark_name = (part.strip() for part in parts)
        normalized = (piece_id, edge_id, landmark_name)
        if normalized in seen_descriptors:
            raise ValueError("duplicate avatar anchor descriptor: {}".format(record))
        seen_descriptors.add(normalized)
        data = panel_data.get(piece_id)
        if data is None:
            raise ValueError("avatar anchor references an unknown pattern piece: {}".format(piece_id))
        edge_ids = tuple(str(value) for value in data.get("boundary_edge_ids", ()))
        edge_chains = tuple(
            _indices(chain, "semantic boundary chain") for chain in data.get("boundary_edges", ())
        )
        if len(edge_ids) != len(edge_chains):
            raise ValueError("pattern piece boundary IDs and vertex chains have different lengths")
        if edge_ids.count(edge_id) != 1:
            raise ValueError(
                "avatar anchor semantic edge is missing or ambiguous: {}:{}".format(piece_id, edge_id)
            )
        chain = edge_chains[edge_ids.index(edge_id)]
        landmark = landmarks.get(landmark_name)
        if landmark is None:
            raise ValueError("avatar anchor references an unknown landmark: {}".format(landmark_name))
        target_position = _point(landmark, "avatar landmark")
        index = select_attachment_particle_near_anchor(chain, points, target_position)
        if index in used_vertices:
            raise ValueError("multiple avatar anchor descriptors resolve to the same cloth particle")
        used_vertices.add(index)
        # A shoulder seam joins the front and back panels at the same lateral skin
        # point. Project both descriptors for a named shoulder in the same outward
        # direction; using the panel's +/-Y depth would pin the seam to opposite sides
        # of the torso and prevent the sewn shoulder edges from converging.
        if landmark_name == "shoulder_right":
            projection_direction = (1.0, 0.0, 0.0)
        elif landmark_name == "shoulder_left":
            projection_direction = (-1.0, 0.0, 0.0)
        else:
            depth_delta = points[index][1] - target_position[1]
            if abs(depth_delta) <= 1e-6:
                raise ValueError(
                    "avatar anchor does not establish the front/back side of the garment piece: {}".format(
                        record
                    )
                )
            projection_direction = (0.0, 1.0 if depth_delta > 0.0 else -1.0, 0.0)
        result.append(
            ResolvedAttachmentTarget(
                particle_index=index,
                piece_id=piece_id,
                edge_id=edge_id,
                landmark_name=landmark_name,
                target_position=target_position,
                projection_direction=projection_direction,
            )
        )
    return tuple(result)


def resolve_avatar_attachment_indices(descriptors: Any, panel_data: Any, positions: Any, landmarks: Any) -> tuple[int, ...]:
    """Return solver indices for semantic descriptors."""
    return tuple(
        target.particle_index
        for target in resolve_avatar_attachment_targets(descriptors, panel_data, positions, landmarks)
    )

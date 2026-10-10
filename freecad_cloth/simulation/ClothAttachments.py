"""Semantic avatar anchors backed by FreeCAD's native mesh queries.

This module maps named garment edges and avatar landmarks to solver particles.
Directional ray queries use FreeCAD's C++ Mesh API; when those rays are too distant,
the fallback computes the nearest point on the validated target triangles.
"""
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import hypot, isfinite, sqrt
from numbers import Integral

from freecad_cloth.common.ValidationModels import (
    AvatarAttachmentProjectionInput,
    MeshArrays,
    validate_point3d,
)


Point3 = tuple[float, float, float]


def _point(value: object, label: str) -> Point3:
    """Normalize one external point through the shared Pydantic geometry schema."""
    try:
        return validate_point3d(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("{} must be a finite 3D point".format(label)) from exc


def _indices(values: Iterable[object], label: str) -> tuple[int, ...]:
    try:
        raw = tuple(values)
    except TypeError as exc:
        raise ValueError("{} must be an iterable of integer indices".format(label)) from exc
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in raw):
        raise ValueError("{} must contain only integer indices".format(label))
    return tuple(dict.fromkeys(int(value) for value in raw))


def _distance_squared(first: Point3, second: Point3) -> float:
    return sum((first[axis] - second[axis]) ** 2 for axis in range(3))


def _nearest_candidate_index(
    points: tuple[Point3, ...],
    candidates: tuple[int, ...],
    target: Point3,
    max_distance_mm: float,
    tie_tolerance_mm: float,
) -> int:
    """Select a unique nearest particle using standard-library Euclidean norms."""
    ranked = sorted(
        (
            hypot(*(points[index][axis] - target[axis] for axis in range(3))),
            index,
        )
        for index in candidates
    )
    if not ranked:
        raise ValueError("attachment edge chain has no unassigned particles")
    best_distance, best_index = ranked[0]
    if best_distance > max_distance_mm:
        raise ValueError("no particle on the semantic edge is near the avatar landmark")
    if (
        len(ranked) > 1
        and abs(ranked[1][0] - best_distance) <= tie_tolerance_mm
    ):
        raise ValueError("avatar landmark maps ambiguously to multiple edge vertices")
    return best_index


def _nearest_point_on_segment(point: Point3, start: Point3, end: Point3) -> Point3:
    """Return the closest point to point on the finite segment start-end."""
    delta = tuple(end[i] - start[i] for i in range(3))
    length_squared = sum(value * value for value in delta)
    if length_squared <= 1e-24:
        return start
    factor = sum(
        (point[i] - start[i]) * delta[i] for i in range(3)
    ) / length_squared
    factor = max(0.0, min(1.0, factor))
    return tuple(start[i] + factor * delta[i] for i in range(3))


def _closest_point_on_triangle(point: Point3, a: Point3, b: Point3, c: Point3) -> Point3:
    """Return the closest point on a triangle using its Voronoi regions."""
    ab = tuple(b[i] - a[i] for i in range(3))
    ac = tuple(c[i] - a[i] for i in range(3))
    ap = tuple(point[i] - a[i] for i in range(3))

    def dot(first: Point3, second: Point3) -> float:
        return sum(first[i] * second[i] for i in range(3))

    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    if dot(normal, normal) <= 1e-24:
        candidates = (
            _nearest_point_on_segment(point, a, b),
            _nearest_point_on_segment(point, b, c),
            _nearest_point_on_segment(point, c, a),
        )
        return min(candidates, key=lambda candidate: _distance_squared(point, candidate))

    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a

    bp = tuple(point[i] - b[i] for i in range(3))
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return tuple(a[i] + v * ab[i] for i in range(3))

    cp = tuple(point[i] - c[i] for i in range(3))
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return tuple(a[i] + w * ac[i] for i in range(3))

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return tuple(b[i] + w * (c[i] - b[i]) for i in range(3))

    denominator = va + vb + vc
    inverse = 1.0 / denominator
    v, w = vb * inverse, vc * inverse
    return tuple(a[i] + ab[i] * v + ac[i] * w for i in range(3))


def _nearest_surface_point(
    point: Point3,
    vertices: Sequence[Point3],
    triangles: Sequence[tuple[int, int, int]],
    direction: Point3 | None = None,
    max_backward_distance: float = 0.0,
) -> tuple[float, int, Point3]:
    """Find a closest surface point, optionally constrained to a semantic side."""
    direction_unit = None
    if direction is not None:
        direction_length = sqrt(sum(float(value) ** 2 for value in direction))
        if direction_length <= 1e-12:
            raise ValueError("semantic surface projection direction must be non-zero")
        if not isfinite(max_backward_distance) or max_backward_distance < 0.0:
            raise ValueError("semantic surface backward allowance must be finite and non-negative")
        direction_unit = tuple(float(value) / direction_length for value in direction)

    best = None
    for triangle_index, (ia, ib, ic) in enumerate(triangles):
        candidate = _closest_point_on_triangle(
            point, vertices[ia], vertices[ib], vertices[ic]
        )
        if direction_unit is not None:
            signed_distance = sum(
                (candidate[axis] - point[axis]) * direction_unit[axis]
                for axis in range(3)
            )
            if signed_distance < -max_backward_distance - 1e-6:
                continue
        distance_squared = _distance_squared(point, candidate)
        record = (distance_squared, triangle_index, candidate)
        if best is None or record[:2] < best[:2]:
            best = record
    if best is None:
        if direction_unit is not None:
            raise ValueError("DrapeTarget has no surface point on the requested semantic side")
        raise ValueError("DrapeTarget surface has no triangles for nearest-point fallback")
    return sqrt(best[0]), best[1], best[2]

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
    chain: object,
    positions: object,
    anchor: object,
    max_distance_mm: float = 400.0,
    tie_tolerance_mm: float = 1e-6,
    excluded_indices: object=(),
) -> int:
    """Select the unique nearest unassigned vertex on a semantic boundary chain."""
    indices = _indices(chain, "attachment edge chain")
    excluded = set(_indices(excluded_indices, "excluded attachment particles"))
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
    if any(index < 0 or index >= len(points) for index in excluded):
        raise ValueError("excluded attachment particle is outside the solver array")
    candidates = tuple(index for index in indices if index not in excluded)
    if not candidates:
        raise ValueError("attachment edge chain has no unassigned particles")
    return _nearest_candidate_index(points, candidates, target, limit, tie_tolerance)


def project_avatar_attachments(
    positions: object,
    particle_indices: object,
    surface: object,
    offset_mm: float = 3.0,
    max_distance_mm: float = 100.0,
    target_points: object=None,
    projection_directions: object=None,
) -> tuple[tuple[Point3, ...], tuple[AttachmentProjection, ...]]:
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

    request = AvatarAttachmentProjectionInput.model_validate(
        {
            "positions": positions,
            "particle_indices": particle_indices,
            "target_points": target_points or {},
            "projection_directions": projection_directions or {},
            "offset_mm": offset_mm,
            "max_distance_mm": max_distance_mm,
        }
    )
    points = request.positions
    indices = tuple(dict.fromkeys(request.particle_indices))
    supplied_targets = request.target_points
    supplied_directions = request.projection_directions
    offset = request.offset_mm
    maximum_distance = request.max_distance_mm

    try:
        surface.validate()
    except AttributeError as exc:
        raise ValueError("avatar attachment requires a validated DrapeTarget surface") from exc
    validated_surface = MeshArrays.model_validate(
        {"vertices": surface.vertices, "triangles": surface.triangles}
    )
    vertices, triangles = validated_surface.vertices, validated_surface.triangles
    if not triangles:
        raise ValueError("DrapeTarget surface has no triangles")

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

        def _is_on_semantic_side(candidate_point):
            if particle_index not in supplied_directions:
                return True
            signed_distance = sum(
                (candidate_point[axis] - source[axis]) * preferred_direction[axis]
                for axis in range(3)
            )
            return signed_distance >= -offset - 1e-6

        candidates = []
        for direction_index, direction in enumerate(directions):
            hits = native_mesh.nearestFacetOnRay(source, direction)
            direction_candidates = []
            for raw_triangle_index, hit_point in hits.items():
                if isinstance(raw_triangle_index, bool) or not isinstance(raw_triangle_index, Integral):
                    raise ValueError("FreeCAD Mesh returned a non-integer facet index")
                triangle_index = int(raw_triangle_index)
                if not 0 <= triangle_index < len(native_facets):
                    raise ValueError("FreeCAD Mesh returned a facet index outside its topology")
                hit = _point(hit_point, "FreeCAD Mesh ray intersection")
                forward_distance = sum(
                    (hit[axis] - source[axis]) * direction[axis] for axis in range(3)
                )
                if forward_distance < -1e-6:
                    continue
                distance = sqrt(_distance_squared(source, hit))
                direction_candidates.append((distance, triangle_index, hit, direction))

            # The opposite ray is a search fallback, not permission to attach a
            # named front/back landmark to the other side of the mannequin.
            if direction_index > 0 and particle_index in supplied_directions:
                direction_candidates = [
                    candidate
                    for candidate in direction_candidates
                    if _is_on_semantic_side(candidate[2])
                ]

            # Semantic landmarks can be authored on the mannequin's center plane,
            # even when that plane lies outside one side of an asymmetric avatar.
            # If the preferred ray misses entirely, seed it just inside the closest
            # surface and retry that semantic direction before allowing the
            # opposite-side fallback to choose a nearer but incorrect face. When a
            # ray does hit only a distant surface, retain the established distance
            # guard and nearest-triangle fallback behavior.
            if direction_index == 0 and not direction_candidates:
                nearest_distance, nearest_triangle, nearest_point = _nearest_surface_point(
                    source, vertices, triangles
                )
                if nearest_distance <= maximum_distance:
                    raw_normal = native_facets[nearest_triangle].Normal
                    if all(hasattr(raw_normal, axis) for axis in ("x", "y", "z")):
                        normal_components = (
                            float(raw_normal.x), float(raw_normal.y), float(raw_normal.z)
                        )
                    else:
                        normal_components = tuple(float(component) for component in raw_normal)
                    if len(normal_components) != 3:
                        raise ValueError("FreeCAD returned an invalid facet normal for an avatar ray origin")
                    normal_length = sqrt(sum(component * component for component in normal_components))
                    if normal_length <= 1e-12:
                        raise ValueError("FreeCAD returned a degenerate facet normal for an avatar ray origin")
                    normal_components = tuple(component / normal_length for component in normal_components)
                    center_components = (
                        float(center_vector.x), float(center_vector.y), float(center_vector.z)
                    )
                    radial_components = tuple(
                        nearest_point[axis] - center_components[axis] for axis in range(3)
                    )
                    radial_alignment = sum(
                        normal_components[axis] * radial_components[axis] for axis in range(3)
                    )
                    if radial_alignment < -1e-6 or (
                        abs(radial_alignment) <= 1e-6
                        and sum(normal_components[axis] * preferred_direction[axis] for axis in range(3)) < 0.0
                    ):
                        normal_components = tuple(-component for component in normal_components)
                    inward_probe = min(max(offset, 1.0), maximum_distance * 0.25)
                    interior_origin = tuple(
                        nearest_point[axis] - normal_components[axis] * inward_probe
                        for axis in range(3)
                    )
                    interior_hits = native_mesh.nearestFacetOnRay(
                        tuple(interior_origin), direction
                    )
                    interior_candidates = []
                    for raw_triangle_index, hit_point in interior_hits.items():
                        if isinstance(raw_triangle_index, bool) or not isinstance(raw_triangle_index, Integral):
                            raise ValueError("FreeCAD Mesh returned a non-integer facet index")
                        triangle_index = int(raw_triangle_index)
                        if not 0 <= triangle_index < len(native_facets):
                            raise ValueError("FreeCAD Mesh returned a facet index outside its topology")
                        hit = _point(hit_point, "FreeCAD Mesh interior-ray intersection")
                        forward_distance = sum(
                            (hit[axis] - interior_origin[axis]) * direction[axis]
                            for axis in range(3)
                        )
                        if forward_distance < -1e-6 or not _is_on_semantic_side(hit):
                            continue
                        distance = sqrt(_distance_squared(source, hit))
                        interior_candidates.append((distance, triangle_index, hit, direction))
                    close_interior_hits = tuple(
                        candidate for candidate in interior_candidates
                        if candidate[0] <= maximum_distance
                    )
                    if close_interior_hits:
                        candidates = list(close_interior_hits)
                        break

            # A named garment anchor carries a semantic front/back (or left/right)
            # direction. Prefer the first hit along that direction; comparing both
            # sides by distance can pin both panels to the same, slightly nearer side
            # of an asymmetric torso. Try the opposite ray only when the preferred
            # ray has no intersection; the bounded nearest-triangle fallback below
            # still handles landmarks whose preferred ray misses the nearby skin.
            if direction_candidates:
                # Trust the semantic side when it reaches the skin within the
                # existing distance guard. If that ray only finds a distant arm
                # or misses the nearby torso, preserve the opposite-ray and exact
                # nearest-triangle fallback used for outlying landmarks.
                if direction_index == 0 and min(item[0] for item in direction_candidates) <= maximum_distance:
                    candidates = direction_candidates
                    break
                candidates.extend(direction_candidates)
        projection_method = "directional-ray"
        if candidates:
            source_distance, triangle_index, closest, hit_direction = min(
                candidates, key=lambda candidate: (candidate[0], candidate[1])
            )
        else:
            source_distance = float("inf")
            triangle_index = -1
            closest = None
            hit_direction = preferred_direction

        # A directional ray can miss the nearby torso while intersecting a distant
        # arm. In that case, query the exact closest point on the validated triangle
        # surface; the same maximum-distance guard still rejects genuinely remote
        # landmarks. This fallback runs only when ray projection cannot be trusted.
        if source_distance > maximum_distance:
            semantic_direction = (
                preferred_direction if particle_index in supplied_directions else None
            )
            nearest_distance, nearest_triangle, nearest_point = _nearest_surface_point(
                source,
                vertices,
                triangles,
                direction=semantic_direction,
                max_backward_distance=offset if semantic_direction is not None else 0.0,
            )
            if nearest_distance < source_distance:
                source_distance = nearest_distance
                triangle_index = nearest_triangle
                closest = nearest_point
                hit_direction = preferred_direction
                projection_method = "nearest-triangle"

        if closest is None or source_distance > maximum_distance:
            raise ValueError(
                (
                    "avatar attachment is too far from the DrapeTarget surface: {:.2f} mm "
                    "(maximum {:.2f} mm; projection={}; particle_index={}; source={}; "
                    "particle={}; direction={}; outward={}; hit={})"
                ).format(
                    source_distance,
                    maximum_distance,
                    projection_method,
                    particle_index,
                    tuple(round(value, 3) for value in source),
                    tuple(round(value, 3) for value in particle_position),
                    tuple(round(value, 3) for value in hit_direction),
                    preferred_direction,
                    tuple(round(value, 3) for value in closest or ()),
                )
            )

        facet_normal = native_facets[triangle_index].Normal
        # Mesh.Facet.Normal may be a tuple in FreeCAD's Mesh API, while
        # other geometry APIs expose a vector with x/y/z attributes.
        if all(hasattr(facet_normal, axis) for axis in ("x", "y", "z")):
            normal_components = (
                float(facet_normal.x),
                float(facet_normal.y),
                float(facet_normal.z),
            )
        else:
            try:
                normal_components = tuple(float(component) for component in facet_normal)
            except (TypeError, ValueError) as exc:
                raise ValueError("FreeCAD returned an invalid facet normal for an avatar anchor") from exc
        if len(normal_components) != 3:
            raise ValueError("FreeCAD returned an invalid facet normal for an avatar anchor")
        normal = App.Vector(*normal_components)
        if float(normal.Length) <= 1e-12:
            raise ValueError("FreeCAD returned a degenerate facet normal for an avatar anchor")
        normal.normalize()
        closest_vector = App.Vector(*closest)
        radial_vector = closest_vector - center_vector
        if float(radial_vector.Length) > 1e-9:
            radial_vector.normalize()
            radial_alignment = float(normal.dot(radial_vector))
        else:
            radial_alignment = 0.0
        if abs(radial_alignment) > 1e-6:
            if radial_alignment < 0.0:
                normal = -normal
        elif float(normal.dot(outward_vector)) < 0.0:
            # Near the target centre the radial direction is ambiguous, so fall
            # back to the semantic projection direction.
            normal = -normal
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


def resolve_avatar_attachment_targets(
    descriptors: object,
    panel_data: object,
    positions: object,
    landmarks: object,
    selection_positions: Sequence[object] | None = None,
) -> tuple[ResolvedAttachmentTarget, ...]:
    """Resolve anchors against authored vertices while retaining current solver positions."""
    points = tuple(_point(position, "particle position") for position in positions)
    if selection_positions is None:
        selection_points = points
    else:
        selection_points = tuple(
            _point(position, "attachment selection position")
            for position in selection_positions
        )
    if len(selection_points) != len(points):
        raise ValueError("attachment selection positions must match solver positions")
    records = tuple(str(value).strip() for value in (descriptors or ()) if str(value).strip())
    if not records:
        raise ValueError("Avatar Attachment mode requires semantic anchor descriptors")
    result = []
    seen_descriptors = set()
    used_vertices = {}
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
        index = select_attachment_particle_near_anchor(
            chain,
            selection_points,
            target_position,
            excluded_indices=tuple(used_vertices),
        )
        if index in used_vertices:
            raise ValueError(
                "multiple avatar anchor descriptors resolve to the same cloth particle "
                "(particle_index={}; first={}; second={})".format(
                    index, used_vertices[index], record
                )
            )
        used_vertices[index] = record
        # The shoulder and neckline endpoints are sewn between front/back panels,
        # so both descriptors must project to the same lateral skin point. Using the
        # panel's +/-Y depth for neck_left/right opens the shoulder seam at its neck
        # endpoint. Only the unsewn neckline center is panel-side-specific.
        if landmark_name in {"shoulder_right", "neck_right"}:
            projection_direction = (1.0, 0.0, 0.0)
        elif landmark_name in {"shoulder_left", "neck_left"}:
            projection_direction = (-1.0, 0.0, 0.0)
        else:
            # The mapped solver point may already lie on the wrong side of the avatar.
            # Use the authored panel position to retain the front/back side of the
            # neckline when selecting its projection direction.
            depth_delta = selection_points[index][1] - target_position[1]
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


def resolve_avatar_attachment_indices(descriptors: Iterable[str] | None, panel_data: Mapping[str, Mapping[str, object]], positions: Sequence[object], landmarks: Mapping[str, object]) -> tuple[int, ...]:
    """Return solver indices for semantic descriptors."""
    return tuple(
        target.particle_index
        for target in resolve_avatar_attachment_targets(descriptors, panel_data, positions, landmarks)
    )

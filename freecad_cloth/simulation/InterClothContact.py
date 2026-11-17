# Copyright (C) 2026 FreeCAD Cloth contributors
"""Two-sided geometric contact between independently simulated cloth groups.

PositionBasedDynamics 2.2.2 does not register deformable triangle models as
mutual distance-field collision targets. This adapter therefore adds a bounded
edge/triangle contact projection after the native cloth step. It operates on
exact global particle indices and preserves authored seams and pins.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Mapping, Sequence
from typing import NamedTuple

import numpy as np
import numpy.typing as npt
from scipy.spatial import KDTree

type PointArray = npt.NDArray[np.float64]
type TriangleArray = npt.NDArray[np.int64]
type EdgeArray = npt.NDArray[np.int64]

_CONTACT_MEASUREMENT_EPSILON_MM = 0.002


def _emit_contact_diagnostic(message: str) -> None:
    """Emit opt-in flushed contact-stage diagnostics for native acceptance runs."""
    if os.environ.get("CLOTH_INTER_CLOTH_DIAGNOSTICS") == "1":
        sys.stdout.write(f"{message}\\n")
        sys.stdout.flush()


class InterClothContactMetrics(NamedTuple):
    """Measured cross-garment contact projection activity for one solver frame."""

    contact_count: int
    corrected_particle_count: int
    remaining_contact_count: int
    max_penetration_before_mm: float
    max_penetration_after_mm: float


class _SurfaceIndex(NamedTuple):
    """Spatial acceleration data for one independent garment group."""

    triangles: TriangleArray
    triangle_centers: PointArray
    triangle_radii: PointArray
    triangle_tree: KDTree
    edges: EdgeArray
    edge_centers: PointArray
    edge_half_lengths: PointArray
    edge_tree: KDTree


def _closest_point_on_triangle(
    point: PointArray,
    triangle: PointArray,
) -> tuple[PointArray, PointArray, PointArray]:
    """Return the closest point, barycentric weights and unit triangle normal.

    Args:
        point: Query point in world millimetres.
        triangle: Three world-space triangle vertices.

    Returns:
        Closest point, non-negative barycentric weights, and unit face normal.

    Raises:
        ValueError: If the target triangle is degenerate.
    """
    a, b, c = triangle
    ab = b - a
    ac = c - a
    normal = np.cross(ab, ac)
    normal_length = float(np.linalg.norm(normal))
    if normal_length <= 1e-12:
        msg = "inter-cloth collision mesh contains a degenerate triangle"
        raise ValueError(msg)
    unit_normal = normal / normal_length

    barycentric = _barycentric_coordinates(point, triangle)
    if bool(np.all(barycentric >= 0.0)):
        return barycentric @ triangle, barycentric, unit_normal

    candidates: list[tuple[float, PointArray, PointArray]] = []
    for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
        start = triangle[start_index]
        direction = triangle[end_index] - start
        length_squared = float(np.dot(direction, direction))
        factor = (
            float(np.clip(np.dot(point - start, direction) / length_squared, 0.0, 1.0))
            if length_squared > 1e-18
            else 0.0
        )
        closest = start + factor * direction
        weights = np.zeros(3, dtype=np.float64)
        weights[start_index] = 1.0 - factor
        weights[end_index] = factor
        squared_distance = float(np.dot(point - closest, point - closest))
        candidates.append((squared_distance, closest, weights))
    _distance, closest, barycentric = min(candidates, key=lambda item: item[0])
    return closest, barycentric, unit_normal


def _closest_points_on_segments(
    a0: PointArray,
    a1: PointArray,
    b0: PointArray,
    b1: PointArray,
) -> tuple[PointArray, PointArray, float, float]:
    """Return closest points and interpolation factors for two finite segments.

    Args:
        a0: First endpoint of segment A.
        a1: Second endpoint of segment A.
        b0: First endpoint of segment B.
        b1: Second endpoint of segment B.

    Returns:
        Closest point on each segment and their start-to-end interpolation factors.
    """
    direction_a = a1 - a0
    direction_b = b1 - b0
    relative = a0 - b0
    aa = float(np.dot(direction_a, direction_a))
    bb = float(np.dot(direction_b, direction_b))
    ab = float(np.dot(direction_a, direction_b))
    ar = float(np.dot(direction_a, relative))
    br = float(np.dot(direction_b, relative))
    epsilon = 1e-18

    if aa <= epsilon and bb <= epsilon:
        return a0.copy(), b0.copy(), 0.0, 0.0
    if aa <= epsilon:
        factor_b = float(np.clip(br / bb, 0.0, 1.0))
        return a0.copy(), b0 + factor_b * direction_b, 0.0, factor_b
    if bb <= epsilon:
        factor_a = float(np.clip(-ar / aa, 0.0, 1.0))
        return a0 + factor_a * direction_a, b0.copy(), factor_a, 0.0

    denominator = aa * bb - ab * ab
    factor_a = (
        float(np.clip((ab * br - ar * bb) / denominator, 0.0, 1.0))
        if denominator > epsilon
        else 0.0
    )
    factor_b = (ab * factor_a + br) / bb
    if factor_b < 0.0:
        factor_b = 0.0
        factor_a = float(np.clip(-ar / aa, 0.0, 1.0))
    elif factor_b > 1.0:
        factor_b = 1.0
        factor_a = float(np.clip((ab - ar) / aa, 0.0, 1.0))
    return (
        a0 + factor_a * direction_a,
        b0 + factor_b * direction_b,
        factor_a,
        factor_b,
    )


def _barycentric_coordinates(point: PointArray, triangle: PointArray) -> PointArray:
    """Return barycentric coordinates for a point projected into a triangle plane."""
    a, b, c = triangle
    ab = b - a
    ac = c - a
    ap = point - a
    d00 = float(np.dot(ab, ab))
    d01 = float(np.dot(ab, ac))
    d11 = float(np.dot(ac, ac))
    d20 = float(np.dot(ap, ab))
    d21 = float(np.dot(ap, ac))
    denominator = d00 * d11 - d01 * d01
    if denominator <= 1e-18:
        msg = "inter-cloth collision mesh contains a degenerate triangle"
        raise ValueError(msg)
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    return np.asarray((1.0 - v - w, v, w), dtype=np.float64)


def _closest_segment_triangle(
    start: PointArray,
    end: PointArray,
    triangle: PointArray,
) -> tuple[PointArray, PointArray, float, PointArray, PointArray]:
    """Return the closest edge/face points and their barycentric coordinates.

    The query first checks exact segment/plane intersection, then an interior
    plane projection, endpoint/face pairs, and all segment/triangle-edge pairs.
    Unlike vertex or midpoint sampling, this detects an edge piercing the
    interior of a triangle even when no mesh vertex is near the contact.

    Args:
        start: First endpoint of the source cloth edge.
        end: Second endpoint of the source cloth edge.
        triangle: Three target cloth triangle vertices.

    Returns:
        Closest point on the source edge, closest point on the triangle, the
        source edge factor, target triangle barycentric weights, and unit face normal.

    Raises:
        ValueError: If the target triangle is degenerate.
    """
    _unused, _unused_weights, normal = _closest_point_on_triangle(
        triangle[0],
        triangle,
    )
    direction = end - start
    signed_start = float(np.dot(start - triangle[0], normal))
    signed_delta = float(np.dot(direction, normal))
    candidates: list[tuple[float, PointArray, PointArray, float, PointArray]] = []

    if abs(signed_delta) > 1e-12:
        factor = -signed_start / signed_delta
        if 0.0 <= factor <= 1.0:
            point = start + factor * direction
            barycentric = _barycentric_coordinates(point, triangle)
            if float(np.min(barycentric)) >= -1e-10:
                barycentric = np.maximum(barycentric, 0.0)
                barycentric /= float(np.sum(barycentric))
                return point, point.copy(), factor, barycentric, normal

    # The segment may run nearly parallel to the face while its projection lies
    # inside the triangle. The closest point on the segment to the plane is the
    # minimum-distance interior-face candidate.
    factor = (
        float(np.clip(-signed_start / signed_delta, 0.0, 1.0)) if abs(signed_delta) > 1e-12 else 0.5
    )
    edge_point = start + factor * direction
    plane_point = edge_point - float(np.dot(edge_point - triangle[0], normal)) * normal
    barycentric = _barycentric_coordinates(plane_point, triangle)
    if float(np.min(barycentric)) >= -1e-10:
        barycentric = np.maximum(barycentric, 0.0)
        barycentric /= float(np.sum(barycentric))
        candidates.append(
            (
                float(np.dot(edge_point - plane_point, edge_point - plane_point)),
                edge_point,
                plane_point,
                factor,
                barycentric,
            )
        )

    for factor, edge_point in ((0.0, start), (1.0, end)):
        face_point, face_barycentric, _normal = _closest_point_on_triangle(
            edge_point,
            triangle,
        )
        difference = edge_point - face_point
        candidates.append(
            (
                float(np.dot(difference, difference)),
                edge_point.copy(),
                face_point,
                factor,
                face_barycentric,
            )
        )

    for triangle_edge in ((0, 1), (1, 2), (2, 0)):
        face_start = triangle[triangle_edge[0]]
        face_end = triangle[triangle_edge[1]]
        edge_point, face_point, edge_factor, face_factor = _closest_points_on_segments(
            start,
            end,
            face_start,
            face_end,
        )
        face_barycentric = np.zeros(3, dtype=np.float64)
        face_barycentric[triangle_edge[0]] = 1.0 - face_factor
        face_barycentric[triangle_edge[1]] = face_factor
        difference = edge_point - face_point
        candidates.append(
            (
                float(np.dot(difference, difference)),
                edge_point,
                face_point,
                edge_factor,
                face_barycentric,
            )
        )

    _distance, edge_point, face_point, factor, face_barycentric = min(
        candidates,
        key=lambda item: item[0],
    )
    return edge_point, face_point, factor, face_barycentric, normal


def _surface_index(positions: PointArray, triangles: TriangleArray) -> _SurfaceIndex:
    """Build a triangle-centre index and unique edges for one garment group.

    Args:
        positions: Current global particle positions in millimetres.
        triangles: Global triangle indices belonging to one garment group.

    Returns:
        Triangle and edge indexes used for conservative contact candidate search.

    Raises:
        ValueError: If the group has no valid triangles or contains degenerate faces.
    """
    if triangles.ndim != 2 or triangles.shape[1] != 3 or triangles.size == 0:
        msg = "each inter-cloth group must contain at least one triangle"
        raise ValueError(msg)
    triangle_points = positions[triangles]
    cross_products = np.cross(
        triangle_points[:, 1] - triangle_points[:, 0],
        triangle_points[:, 2] - triangle_points[:, 0],
    )
    if bool(np.any(np.linalg.norm(cross_products, axis=1) <= 1e-12)):
        msg = "inter-cloth collision mesh contains a degenerate triangle"
        raise ValueError(msg)
    triangle_centers = triangle_points.mean(axis=1)
    triangle_radii = np.linalg.norm(
        triangle_points - triangle_centers[:, None, :],
        axis=2,
    ).max(axis=1)
    triangle_tree = KDTree(triangle_centers)

    directed_edges = np.concatenate(
        (triangles[:, (0, 1)], triangles[:, (1, 2)], triangles[:, (2, 0)]),
        axis=0,
    )
    edges = np.unique(np.sort(directed_edges, axis=1), axis=0)
    edge_points = positions[edges]
    edge_centers = edge_points.mean(axis=1)
    edge_half_lengths = np.linalg.norm(edge_points[:, 1] - edge_points[:, 0], axis=1) * 0.5
    edge_tree = KDTree(edge_centers)
    return _SurfaceIndex(
        triangles,
        triangle_centers,
        triangle_radii,
        triangle_tree,
        edges,
        edge_centers,
        edge_half_lengths,
        edge_tree,
    )


def _stitch_clusters(
    particle_count: int,
    stitches: Sequence[tuple[int, int]],
) -> tuple[tuple[int, ...], ...]:
    """Resolve sewn-particle components so a contact correction cannot open a seam.

    Args:
        particle_count: Number of particles in the combined cloth system.
        stitches: Exact global particle-index pairs for authored seams.

    Returns:
        Disjoint groups of particles connected by one or more stitch constraints.

    Raises:
        ValueError: If a stitch index is outside the combined particle array.
    """
    parent = list(range(particle_count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for raw_left, raw_right in stitches:
        left, right = int(raw_left), int(raw_right)
        if not 0 <= left < particle_count or not 0 <= right < particle_count:
            msg = "inter-cloth stitch index is outside the particle array"
            raise ValueError(msg)
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    members: dict[int, set[int]] = {}
    for raw_left, raw_right in stitches:
        for index in (int(raw_left), int(raw_right)):
            members.setdefault(find(index), set()).add(index)
    return tuple(tuple(sorted(group)) for group in members.values() if len(group) > 1)


def _contact_direction(
    normal: PointArray, source_center: PointArray, target_center: PointArray
) -> PointArray:
    """Orient the target face normal toward the source garment's side."""
    direction = np.asarray(normal, dtype=np.float64)
    offset = source_center - target_center
    side = float(np.dot(direction, offset))
    if abs(side) > 1e-10:
        return direction if side > 0.0 else -direction
    nonzero = np.flatnonzero(np.abs(direction) > 1e-12)
    if nonzero.size and direction[int(nonzero[0])] < 0.0:
        direction = -direction
    return direction


def _accumulate_edge_triangle(
    positions: PointArray,
    source_edge: tuple[int, int],
    target_triangle: tuple[int, int, int],
    inverse_masses: PointArray,
    clearance_mm: float,
    source_center: PointArray,
    target_center: PointArray,
    fallback_sign: float,
    correction_sum: PointArray,
    correction_count: npt.NDArray[np.int64],
) -> tuple[bool, float]:
    """Accumulate one two-sided edge/triangle separation constraint."""
    source_ids = np.asarray(source_edge, dtype=np.int64)
    target_ids = np.asarray(target_triangle, dtype=np.int64)
    edge_point, face_point, factor, face_weights, normal = _closest_segment_triangle(
        positions[source_ids[0]],
        positions[source_ids[1]],
        positions[target_ids],
    )
    difference = edge_point - face_point
    distance = float(np.linalg.norm(difference))
    penetration = clearance_mm - distance
    if penetration <= 1e-8:
        return False, 0.0

    if distance > 1e-10:
        direction = difference / distance
    else:
        direction = _contact_direction(normal, source_center, target_center)
        if float(np.linalg.norm(source_center - target_center)) <= 1e-10:
            # Coincident group centroids provide no physical side cue. Use the
            # stable sorted group order so the two directional passes cannot
            # cancel each other's zero-distance correction.
            direction = direction * float(fallback_sign)
    source_weights = np.asarray((1.0 - factor, factor), dtype=np.float64)
    source_masses = inverse_masses[source_ids]
    target_masses = inverse_masses[target_ids]
    denominator = float(
        np.sum(source_masses * source_weights * source_weights)
        + np.sum(target_masses * face_weights * face_weights)
    )
    if denominator <= 1e-15:
        return False, penetration

    multiplier = penetration / denominator
    for local_index, particle_index in enumerate(source_ids):
        weight = float(source_masses[local_index] * source_weights[local_index])
        if weight <= 0.0:
            continue
        correction_sum[particle_index] += direction * weight * multiplier
        correction_count[particle_index] += 1
    for local_index, particle_index in enumerate(target_ids):
        weight = float(target_masses[local_index] * face_weights[local_index])
        if weight <= 0.0:
            continue
        correction_sum[particle_index] -= direction * weight * multiplier
        correction_count[particle_index] += 1
    return True, penetration


def _share_sewn_corrections(
    corrections: PointArray,
    inverse_masses: PointArray,
    clusters: Sequence[Sequence[int]],
) -> None:
    """Give every movable particle in one stitch component the same correction."""
    for cluster in clusters:
        indices = np.asarray(cluster, dtype=np.int64)
        if bool(np.any(inverse_masses[indices] <= 0.0)):
            corrections[indices] = 0.0
            continue
        corrections[indices] = corrections[indices].mean(axis=0)


def _index_garment_surfaces(
    positions: PointArray,
    triangles_by_group: Mapping[str, Sequence[Sequence[int]]],
    *,
    operation: str,
) -> tuple[dict[str, _SurfaceIndex], dict[int, str]]:
    """Validate isolated garment topology and build one spatial index per group.

    Args:
        positions: Global current solver particle positions in millimetres.
        triangles_by_group: Triangle indices keyed by independent garment ID.
        operation: Name of the public operation requesting these indexes.

    Returns:
        Surface indexes and a mapping from every referenced particle to its group.
    """
    if len(triangles_by_group) < 2:
        msg = f"inter-cloth {operation} requires at least two independent garment groups"
        raise ValueError(msg)
    surfaces: dict[str, _SurfaceIndex] = {}
    particle_owners: dict[int, str] = {}
    for raw_group_id, raw_triangles in triangles_by_group.items():
        group_id = str(raw_group_id).strip()
        if not group_id or group_id in surfaces:
            msg = "inter-cloth group IDs must be non-empty and unique"
            raise ValueError(msg)
        triangles = np.asarray(raw_triangles, dtype=np.int64)
        if triangles.ndim != 2 or triangles.shape[1] != 3 or triangles.size == 0:
            msg = f"inter-cloth group {group_id!r} has no valid triangles"
            raise ValueError(msg)
        if bool(np.any(triangles < 0)) or bool(np.any(triangles >= len(positions))):
            msg = f"inter-cloth group {group_id!r} references a missing particle"
            raise ValueError(msg)
        for raw_index in np.unique(triangles):
            particle_index = int(raw_index)
            previous = particle_owners.setdefault(particle_index, group_id)
            if previous != group_id:
                msg = "independent inter-cloth groups must not share solver particles"
                raise ValueError(msg)
        surfaces[group_id] = _surface_index(positions, triangles)
    return surfaces, particle_owners


def _measure_contacts(
    positions: PointArray,
    surfaces: Mapping[str, _SurfaceIndex],
    clearance_mm: float,
) -> tuple[int, float]:
    """Measure residual clearance deficits greater than the 0.002 mm numeric tolerance."""
    group_ids = tuple(sorted(surfaces))
    contact_count = 0
    maximum = 0.0
    for left_index, left_id in enumerate(group_ids):
        left = surfaces[left_id]
        for right_id in group_ids[left_index + 1 :]:
            right = surfaces[right_id]
            for source, target in ((left, right), (right, left)):
                for edge_index, edge in enumerate(source.edges):
                    radius = (
                        clearance_mm
                        + float(source.edge_half_lengths[edge_index])
                        + float(target.triangle_radii.max())
                    )
                    candidates = target.triangle_tree.query_ball_point(
                        source.edge_centers[edge_index],
                        radius,
                    )
                    for triangle_index in candidates:
                        triangle = target.triangles[int(triangle_index)]
                        edge_point, face_point, _factor, _weights, _normal = (
                            _closest_segment_triangle(
                                positions[int(edge[0])],
                                positions[int(edge[1])],
                                positions[triangle],
                            )
                        )
                        penetration = clearance_mm - float(np.linalg.norm(edge_point - face_point))
                        if penetration > _CONTACT_MEASUREMENT_EPSILON_MM:
                            contact_count += 1
                            maximum = max(maximum, penetration)
    return contact_count, maximum


def measure_inter_cloth_contacts(
    positions_mm: npt.ArrayLike,
    triangles_by_group: Mapping[str, Sequence[Sequence[int]]],
    *,
    clearance_mm: float,
) -> tuple[int, float]:
    """Measure residual clearance deficits between independent garment groups.

    A positive deficit means the closest sampled edge/triangle distance is
    smaller than the requested clearance. It is not a signed volumetric
    intersection depth.

    Args:
        positions_mm: Current global solver particle positions in millimetres.
        triangles_by_group: Global triangle indices keyed by independent garment ID.
        clearance_mm: Minimum requested surface separation.

    Returns:
        Number of residual edge/triangle pairs whose clearance deficit exceeds
        the 0.002 mm numerical tolerance and their maximum deficit in millimetres.

    Raises:
        ValueError: If positions, triangle indices, garment identities or clearance
            are invalid.
    """
    positions = np.asarray(positions_mm, dtype=np.float64)
    clearance = float(clearance_mm)
    if positions.ndim != 2 or positions.shape[1] != 3 or positions.shape[0] == 0:
        msg = "inter-cloth positions must be a non-empty array with shape (N, 3)"
        raise ValueError(msg)
    if not bool(np.isfinite(positions).all()):
        msg = "inter-cloth positions must be finite"
        raise ValueError(msg)
    if not np.isfinite(clearance) or clearance <= 0.0:
        msg = "inter-cloth clearance must be positive and finite"
        raise ValueError(msg)
    surfaces, _ = _index_garment_surfaces(positions, triangles_by_group, operation="measurement")
    return _measure_contacts(positions, surfaces, clearance)


def project_inter_cloth_contacts(
    positions_mm: npt.ArrayLike,
    triangles_by_group: Mapping[str, Sequence[Sequence[int]]],
    inverse_masses: npt.ArrayLike,
    *,
    clearance_mm: float,
    stitches: Sequence[tuple[int, int]] = (),
    iterations: int = 8,
    relaxation: float = 0.8,
) -> tuple[PointArray, PointArray, InterClothContactMetrics]:
    """Project distinct garment groups apart using two-sided edge/face contacts.

    Every unique source edge is tested against nearby target triangles in both
    group directions. The closest edge and face points define a weighted
    separation constraint distributed over their real solver particles. This
    catches edge/face crossings without relying on rendered overlap or vertex
    proximity alone. Only explicitly distinct group IDs interact.

    Args:
        positions_mm: Current global particle positions in FreeCAD millimetres.
        triangles_by_group: Global triangle indices keyed by independent garment ID.
        inverse_masses: Per-particle inverse mass; zero denotes a fixed particle.
        clearance_mm: Minimum requested separation between garment surfaces.
        stitches: Exact global particle pairs used by authored sewing constraints.
        iterations: Bounded number of position-projection passes (1 through 16).
        relaxation: Fraction of each accumulated correction applied per pass.

    Returns:
        Corrected particle positions, normalized actual correction directions,
        and contact metrics for this projection frame.

    Raises:
        ValueError: If geometry, group identity, masses, clearance or solver settings are invalid.
    """
    positions = np.asarray(positions_mm, dtype=np.float64)
    masses = np.asarray(inverse_masses, dtype=np.float64)
    clearance = float(clearance_mm)
    pass_count = int(iterations)
    alpha = float(relaxation)
    if positions.ndim != 2 or positions.shape[1] != 3 or positions.shape[0] == 0:
        msg = "inter-cloth positions must be a non-empty array with shape (N, 3)"
        raise ValueError(msg)
    if masses.shape != (len(positions),):
        msg = "inter-cloth inverse masses must match the particle count"
        raise ValueError(msg)
    if not bool(np.isfinite(positions).all() and np.isfinite(masses).all()):
        msg = "inter-cloth positions and inverse masses must be finite"
        raise ValueError(msg)
    if bool(np.any(masses < 0.0)):
        msg = "inter-cloth inverse masses cannot be negative"
        raise ValueError(msg)
    if not np.isfinite(clearance) or clearance <= 0.0:
        msg = "inter-cloth clearance must be positive and finite"
        raise ValueError(msg)
    if pass_count < 1 or pass_count > 16:
        msg = "inter-cloth projection iterations must be between 1 and 16"
        raise ValueError(msg)
    if not np.isfinite(alpha) or not 0.0 < alpha <= 1.0:
        msg = "inter-cloth relaxation must be in (0, 1]"
        raise ValueError(msg)
    surfaces, particle_owners = _index_garment_surfaces(
        positions, triangles_by_group, operation="projection"
    )
    group_ids = tuple(sorted(surfaces))
    _emit_contact_diagnostic(
        "inter-cloth-indexed "
        f"particles={len(positions)} "
        + " ".join(
            f"group={group_id}:triangles={len(surfaces[group_id].triangles)}:edges={len(surfaces[group_id].edges)}"
            for group_id in group_ids
        )
    )
    for raw_left, raw_right in stitches:
        left, right = int(raw_left), int(raw_right)
        left_group = particle_owners.get(left)
        right_group = particle_owners.get(right)
        if left_group is not None and right_group is not None and left_group != right_group:
            msg = "authored stitches cannot connect independent garment groups"
            raise ValueError(msg)
    clusters = _stitch_clusters(len(positions), stitches)
    original = positions.copy()
    current = positions.copy()
    contacts_before = 0
    maximum_before = 0.0

    for iteration in range(pass_count):
        pass_started = time.perf_counter()
        _emit_contact_diagnostic(f"inter-cloth-pass-start iteration={iteration + 1}")
        surfaces = {
            group_id: _surface_index(current, surface.triangles)
            for group_id, surface in surfaces.items()
        }
        correction_sum = np.zeros_like(current)
        correction_count = np.zeros(len(current), dtype=np.int64)
        contacts_this_pass = 0
        maximum_this_pass = 0.0

        for left_index, left_id in enumerate(group_ids):
            left = surfaces[left_id]
            for right_id in group_ids[left_index + 1 :]:
                right = surfaces[right_id]
                for direction_index, (source, target, fallback_sign) in enumerate(
                    (
                        (left, right, 1.0),
                        (right, left, -1.0),
                    )
                ):
                    direction_started = time.perf_counter()
                    candidate_count = 0
                    _emit_contact_diagnostic(
                        f"inter-cloth-direction-start iteration={iteration + 1} "
                        f"source_edges={len(source.edges)} target_triangles={len(target.triangles)} "
                        f"direction={direction_index}"
                    )
                    source_center = current[np.unique(source.triangles)].mean(axis=0)
                    target_center = current[np.unique(target.triangles)].mean(axis=0)
                    for edge_index, edge in enumerate(source.edges):
                        query_radius = (
                            clearance
                            + float(source.edge_half_lengths[edge_index])
                            + float(target.triangle_radii.max())
                        )
                        candidates = target.triangle_tree.query_ball_point(
                            source.edge_centers[edge_index],
                            query_radius,
                        )
                        candidate_count += len(candidates)
                        if edge_index > 0 and edge_index % 5000 == 0:
                            _emit_contact_diagnostic(
                                f"inter-cloth-direction-progress iteration={iteration + 1} "
                                f"direction={direction_index} edges={edge_index}/{len(source.edges)} "
                                f"candidates={candidate_count} elapsed_s={time.perf_counter() - direction_started:.1f}"
                            )
                        for triangle_index in candidates:
                            triangle: tuple[int, int, int] = (
                                int(target.triangles[int(triangle_index), 0]),
                                int(target.triangles[int(triangle_index), 1]),
                                int(target.triangles[int(triangle_index), 2]),
                            )
                            contact, penetration = _accumulate_edge_triangle(
                                current,
                                (int(edge[0]), int(edge[1])),
                                triangle,
                                masses,
                                clearance,
                                source_center,
                                target_center,
                                fallback_sign,
                                correction_sum,
                                correction_count,
                            )
                            contacts_this_pass += int(contact)
                            maximum_this_pass = max(
                                maximum_this_pass,
                                penetration if contact else 0.0,
                            )
                    _emit_contact_diagnostic(
                        f"inter-cloth-direction-finish iteration={iteration + 1} "
                        f"direction={direction_index} candidates={candidate_count} "
                        f"elapsed_s={time.perf_counter() - direction_started:.1f}"
                    )

        corrections = np.divide(
            correction_sum,
            correction_count[:, None],
            out=np.zeros_like(correction_sum),
            where=correction_count[:, None] > 0,
        )
        _share_sewn_corrections(corrections, masses, clusters)
        moved = np.linalg.norm(corrections, axis=1) > 1e-10
        current += alpha * corrections
        if iteration == 0:
            contacts_before = contacts_this_pass
            maximum_before = maximum_this_pass
        _emit_contact_diagnostic(
            f"inter-cloth-pass-finish iteration={iteration + 1} "
            f"contacts={contacts_this_pass} moved={int(np.count_nonzero(moved))} "
            f"elapsed_s={time.perf_counter() - pass_started:.1f}"
        )
        if not bool(np.any(moved)):
            break

    surfaces = {
        group_id: _surface_index(current, surface.triangles)
        for group_id, surface in surfaces.items()
    }
    _emit_contact_diagnostic("inter-cloth-residual-measure-start")
    remaining_contacts, maximum_after = _measure_contacts(current, surfaces, clearance)
    _emit_contact_diagnostic(
        f"inter-cloth-residual-measure-finish remaining={remaining_contacts} max_deficit_mm={maximum_after:.4f}"
    )
    movement = np.linalg.norm(current - original, axis=1)
    corrected_count = int(np.count_nonzero(movement > 1e-8))
    directions = np.zeros_like(current)
    moved = movement > 1e-8
    directions[moved] = (current[moved] - original[moved]) / movement[moved, None]
    metrics = InterClothContactMetrics(
        contacts_before,
        corrected_count,
        remaining_contacts,
        maximum_before,
        maximum_after,
    )
    return current, directions, metrics

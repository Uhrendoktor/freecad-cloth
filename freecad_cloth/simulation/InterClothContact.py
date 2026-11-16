# Copyright (C) 2026 FreeCAD Cloth contributors
"""Two-sided position-level contact between independently simulated cloth groups.

PositionBasedDynamics 2.2.2 does not currently register deformable triangle models
as mutual distance-field collision targets. This adapter supplies a bounded
point/triangle plus edge/edge contact projection after each native cloth step.
It is deliberately solver-neutral and accepts exact global particle indices.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NamedTuple

import numpy as np
import numpy.typing as npt
from scipy.spatial import KDTree

type PointArray = npt.NDArray[np.float64]
type TriangleArray = npt.NDArray[np.int64]
type EdgeArray = npt.NDArray[np.int64]


class InterClothContactMetrics(NamedTuple):
    """Measured inter-cloth projection activity for one solver frame."""

    contact_count: int
    corrected_particle_count: int
    remaining_contact_count: int
    max_penetration_before_mm: float
    max_penetration_after_mm: float


class _SurfaceIndex(NamedTuple):
    """Indexed triangles and edges belonging to one independent garment group."""

    triangles: TriangleArray
    triangle_centers: PointArray
    triangle_radii: PointArray
    triangle_tree: KDTree
    edges: EdgeArray
    edge_centers: PointArray
    edge_half_lengths: PointArray
    edge_tree: KDTree


def _canonical_direction(vector: PointArray) -> PointArray:
    """Return a normalized direction with deterministic sign.

    Args:
        vector: Candidate normal or direction vector.

    Returns:
        A unit vector whose first significant component is positive.

    Raises:
        ValueError: If the vector has no finite, non-zero length.
    """
    length = float(np.linalg.norm(vector))
    if not np.isfinite(length) or length <= 1e-12:
        msg = "contact fallback direction must be finite and non-zero"
        raise ValueError(msg)
    direction = np.asarray(vector / length, dtype=np.float64)
    nonzero = np.flatnonzero(np.abs(direction) > 1e-12)
    if nonzero.size and direction[int(nonzero[0])] < 0.0:
        direction = -direction
    return direction


def _closest_point_on_segment(
    point: PointArray,
    start: PointArray,
    end: PointArray,
) -> tuple[PointArray, float]:
    """Return the closest point and interpolation factor on a finite segment.

    Args:
        point: Query point in world millimetres.
        start: First segment endpoint.
        end: Second segment endpoint.

    Returns:
        Closest point and clamped interpolation factor from start to end.
    """
    direction = end - start
    length_squared = float(np.dot(direction, direction))
    if length_squared <= 1e-18:
        return start.copy(), 0.0
    factor = float(np.clip(np.dot(point - start, direction) / length_squared, 0.0, 1.0))
    return start + factor * direction, factor


def _closest_point_on_triangle(
    point: PointArray,
    triangle: PointArray,
) -> tuple[PointArray, PointArray, PointArray]:
    """Return a closest point, barycentric weights and triangle normal.

    The plane projection is used when it lies inside the triangle. Otherwise,
    the closest of the three finite edges is used. All returned weights are
    non-negative and sum to one, including edge and vertex contacts.

    Args:
        point: Query point in world millimetres.
        triangle: Three world-space triangle vertices.

    Returns:
        Closest point, three barycentric weights, and unit face normal.

    Raises:
        ValueError: If the triangle is degenerate.
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

    d00 = float(np.dot(ab, ab))
    d01 = float(np.dot(ab, ac))
    d11 = float(np.dot(ac, ac))
    ap = point - a
    d20 = float(np.dot(ap, ab))
    d21 = float(np.dot(ap, ac))
    denominator = d00 * d11 - d01 * d01
    if denominator <= 1e-18:
        msg = "inter-cloth collision mesh contains a degenerate triangle"
        raise ValueError(msg)
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    u = 1.0 - v - w
    if min(u, v, w) >= 0.0:
        barycentric = np.asarray((u, v, w), dtype=np.float64)
        closest = u * a + v * b + w * c
        return closest, barycentric, unit_normal

    candidates: list[tuple[float, PointArray, PointArray]] = []
    for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
        closest, factor = _closest_point_on_segment(
            point,
            triangle[start_index],
            triangle[end_index],
        )
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
    """Return closest points and segment factors for two finite 3D edges.

    Args:
        a0: First endpoint of segment A.
        a1: Second endpoint of segment A.
        b0: First endpoint of segment B.
        b1: Second endpoint of segment B.

    Returns:
        Closest point on A, closest point on B, and their segment factors.
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


def _surface_index(positions: PointArray, triangles: TriangleArray) -> _SurfaceIndex:
    """Build local spatial indexes for one garment surface.

    Args:
        positions: All global particle positions.
        triangles: Global triangle indices belonging to one garment group.

    Returns:
        Triangle and edge centroid indexes with conservative query radii.

    Raises:
        ValueError: If the group has no valid, non-degenerate triangles.
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
    """Resolve connected groups of sewn particles for shared contact corrections.

    Args:
        particle_count: Number of particles in the combined cloth system.
        stitches: Exact global solver particle pairs belonging to authored seams.

    Returns:
        Disjoint sewn-particle groups, omitting isolated particles.

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

    members: dict[int, list[int]] = {}
    for raw_left, raw_right in stitches:
        for index in (int(raw_left), int(raw_right)):
            members.setdefault(find(index), []).append(index)
    return tuple(
        tuple(sorted(set(group)))
        for group in members.values()
        if len(set(group)) > 1
    )


def _accumulate_point_triangle(
    positions: PointArray,
    source_index: int,
    target_triangle: tuple[int, int, int],
    inverse_masses: PointArray,
    clearance_mm: float,
    fallback_direction: PointArray,
    correction_sum: PointArray,
    correction_count: npt.NDArray[np.int64],
) -> tuple[bool, float]:
    """Accumulate one two-sided particle/triangle separation constraint."""
    target_ids = np.asarray(target_triangle, dtype=np.int64)
    closest, barycentric, normal = _closest_point_on_triangle(
        positions[source_index],
        positions[target_ids],
    )
    difference = positions[source_index] - closest
    distance = float(np.linalg.norm(difference))
    penetration = clearance_mm - distance
    if penetration <= 1e-8:
        return False, 0.0

    direction = difference / distance if distance > 1e-10 else fallback_direction * normal
    source_weight = float(inverse_masses[source_index])
    target_weights = inverse_masses[target_ids]
    denominator = source_weight + float(np.sum(target_weights * barycentric * barycentric))
    if denominator <= 1e-15:
        return False, penetration

    multiplier = penetration / denominator
    correction_sum[source_index] += direction * source_weight * multiplier
    correction_count[source_index] += int(source_weight > 0.0)
    for local_index, particle_index in enumerate(target_ids):
        weight = float(target_weights[local_index] * barycentric[local_index])
        if weight <= 0.0:
            continue
        correction_sum[particle_index] -= direction * weight * multiplier
        correction_count[particle_index] += 1
    return True, penetration


def _accumulate_edge_edge(
    positions: PointArray,
    edge_a: tuple[int, int],
    edge_b: tuple[int, int],
    inverse_masses: PointArray,
    clearance_mm: float,
    fallback_direction: PointArray,
    correction_sum: PointArray,
    correction_count: npt.NDArray[np.int64],
) -> tuple[bool, float]:
    """Accumulate one two-sided closest-segment separation constraint."""
    ids_a = np.asarray(edge_a, dtype=np.int64)
    ids_b = np.asarray(edge_b, dtype=np.int64)
    point_a, point_b, factor_a, factor_b = _closest_points_on_segments(
        positions[ids_a[0]],
        positions[ids_a[1]],
        positions[ids_b[0]],
        positions[ids_b[1]],
    )
    difference = point_b - point_a
    distance = float(np.linalg.norm(difference))
    penetration = clearance_mm - distance
    if penetration <= 1e-8:
        return False, 0.0
    direction = difference / distance if distance > 1e-10 else fallback_direction

    weights_a = np.asarray((1.0 - factor_a, factor_a), dtype=np.float64)
    weights_b = np.asarray((1.0 - factor_b, factor_b), dtype=np.float64)
    masses_a = inverse_masses[ids_a]
    masses_b = inverse_masses[ids_b]
    denominator = float(
        np.sum(masses_a * weights_a * weights_a)
        + np.sum(masses_b * weights_b * weights_b)
    )
    if denominator <= 1e-15:
        return False, penetration

    multiplier = penetration / denominator
    for index, particle_index in enumerate(ids_a):
        weight = float(masses_a[index] * weights_a[index])
        if weight <= 0.0:
            continue
        correction_sum[particle_index] -= direction * weight * multiplier
        correction_count[particle_index] += 1
    for index, particle_index in enumerate(ids_b):
        weight = float(masses_b[index] * weights_b[index])
        if weight <= 0.0:
            continue
        correction_sum[particle_index] += direction * weight * multiplier
        correction_count[particle_index] += 1
    return True, penetration


def _share_sewn_corrections(
    corrections: PointArray,
    inverse_masses: PointArray,
    clusters: Sequence[Sequence[int]],
) -> None:
    """Give all movable endpoints in each seam component the same correction."""
    for cluster in clusters:
        indices = np.asarray(cluster, dtype=np.int64)
        if bool(np.any(inverse_masses[indices] <= 0.0)):
            corrections[indices] = 0.0
            continue
        shared = corrections[indices].mean(axis=0)
        corrections[indices] = shared


def _candidate_contact_statistics(
    positions: PointArray,
    surfaces: Mapping[str, _SurfaceIndex],
    clearance_mm: float,
) -> tuple[int, float]:
    """Measure remaining point/triangle and edge/edge penetrations."""
    group_ids = tuple(sorted(surfaces))
    contact_count = 0
    max_penetration = 0.0
    for left_index, left_id in enumerate(group_ids):
        left = surfaces[left_id]
        for right_id in group_ids[left_index + 1 :]:
            right = surfaces[right_id]
            for source, target in (
                (left, right),
                (right, left),
            ):
                source_vertices = np.unique(source.triangles)
                query_radius = clearance_mm + float(target.triangle_radii.max())
                for source_particle in source_vertices:
                    candidate_ids = target.triangle_tree.query_ball_point(
                        positions[int(source_particle)],
                        query_radius,
                    )
                    for triangle_id in candidate_ids:
                        ids = target.triangles[int(triangle_id)]
                        closest, _barycentric, _normal = _closest_point_on_triangle(
                            positions[int(source_particle)],
                            positions[ids],
                        )
                        distance = float(np.linalg.norm(positions[int(source_particle)] - closest))
                        penetration = clearance_mm - distance
                        if penetration > 1e-8:
                            contact_count += 1
                            max_penetration = max(max_penetration, penetration)

            query_radius = (
                clearance_mm
                + float(left.edge_half_lengths.max())
                + float(right.edge_half_lengths.max())
            )
            for edge_index, center in enumerate(left.edge_centers):
                candidate_ids = right.edge_tree.query_ball_point(center, query_radius)
                radius_a = float(left.edge_half_lengths[edge_index])
                for edge_id in candidate_ids:
                    radius = clearance_mm + radius_a + float(right.edge_half_lengths[int(edge_id)])
                    if float(np.linalg.norm(center - right.edge_centers[int(edge_id)])) > radius:
                        continue
                    edge_a = left.edges[edge_index]
                    edge_b = right.edges[int(edge_id)]
                    point_a, point_b, _factor_a, _factor_b = _closest_points_on_segments(
                        positions[edge_a[0]],
                        positions[edge_a[1]],
                        positions[edge_b[0]],
                        positions[edge_b[1]],
                    )
                    penetration = clearance_mm - float(np.linalg.norm(point_b - point_a))
                    if penetration > 1e-8:
                        contact_count += 1
                        max_penetration = max(max_penetration, penetration)
    return contact_count, max_penetration


def project_inter_cloth_contacts(
    positions_mm: npt.ArrayLike,
    triangles_by_group: Mapping[str, Sequence[Sequence[int]]],
    inverse_masses: npt.ArrayLike,
    *,
    clearance_mm: float,
    stitches: Sequence[tuple[int, int]] = (),
    iterations: int = 3,
    relaxation: float = 0.8,
) -> tuple[PointArray, PointArray, InterClothContactMetrics]:
    """Project independent cloth groups apart using point/triangle and edge contacts.

    Each group may contain several sewn pattern panels, but contacts are generated
    only between distinct group IDs. The projection is symmetric: particles from
    each group are tested against the other group's triangles, and unique edges
    from both groups are tested against one another. Stitch-connected particles
    receive a shared correction, and a cluster containing a pinned particle is
    not moved. This protects seam correspondence and fixed anchors during contact.

    Args:
        positions_mm: Current global particle positions in FreeCAD millimetres.
        triangles_by_group: Non-empty global triangle lists keyed by garment-group ID.
        inverse_masses: Per-particle inverse mass; zero denotes a fixed particle.
        clearance_mm: Minimum requested distance between independent cloth surfaces.
        stitches: Exact global particle pairs used by the sewing solver.
        iterations: Number of bounded contact-projection passes.
        relaxation: Fraction of each computed correction applied per pass.

    Returns:
        Corrected positions, per-particle outward correction directions, and contact metrics.

    Raises:
        ValueError: If coordinates, groups, indices, masses, clearance, or iteration settings are invalid.
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
    if len(triangles_by_group) < 2:
        msg = "inter-cloth projection requires at least two independent garment groups"
        raise ValueError(msg)

    surfaces: dict[str, _SurfaceIndex] = {}
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
        surfaces[group_id] = _surface_index(positions, triangles)

    group_ids = tuple(sorted(surfaces))
    particle_owners: dict[int, str] = {}
    for group_id, surface in surfaces.items():
        for particle_index in np.unique(surface.triangles):
            index = int(particle_index)
            previous = particle_owners.setdefault(index, group_id)
            if previous != group_id:
                msg = "independent inter-cloth groups must not share solver particles"
                raise ValueError(msg)
    clusters = _stitch_clusters(len(positions), stitches)
    original = positions.copy()
    current = positions.copy()
    correction_directions = np.zeros_like(current)
    contacts_before = 0
    max_penetration_before = 0.0

    for _iteration in range(pass_count):
        correction_sum = np.zeros_like(current)
        correction_count = np.zeros(len(current), dtype=np.int64)
        contacts_this_pass = 0
        max_penetration_this_pass = 0.0

        for left_index, left_id in enumerate(group_ids):
            left = surfaces[left_id]
            left_vertices = np.unique(left.triangles)
            for right_id in group_ids[left_index + 1 :]:
                right = surfaces[right_id]

                for source_group_index, source, target in (
                    (left_index, left, right),
                    (left_index + 1, right, left),
                ):
                    fallback_sign = 1.0 if source_group_index == left_index else -1.0
                    for source_particle in np.unique(source.triangles):
                        query_radius = clearance + float(target.triangle_radii.max())
                        candidate_ids = target.triangle_tree.query_ball_point(
                            current[int(source_particle)],
                            query_radius,
                        )
                        for triangle_id in candidate_ids:
                            triangle_ids = tuple(int(value) for value in target.triangles[int(triangle_id)])
                            triangle_points = current[np.asarray(triangle_ids, dtype=np.int64)]
                            fallback = fallback_sign * _canonical_direction(
                                np.cross(
                                    triangle_points[1] - triangle_points[0],
                                    triangle_points[2] - triangle_points[0],
                                )
                            )
                            contact, penetration = _accumulate_point_triangle(
                                current,
                                int(source_particle),
                                triangle_ids,
                                masses,
                                clearance,
                                fallback,
                                correction_sum,
                                correction_count,
                            )
                            contacts_this_pass += int(contact)
                            max_penetration_this_pass = max(
                                max_penetration_this_pass,
                                penetration if contact else 0.0,
                            )

                query_radius = (
                    clearance
                    + float(left.edge_half_lengths.max())
                    + float(right.edge_half_lengths.max())
                )
                for edge_index, center in enumerate(left.edge_centers):
                    candidates = right.edge_tree.query_ball_point(center, query_radius)
                    edge_a = tuple(int(value) for value in left.edges[edge_index])
                    radius_a = float(left.edge_half_lengths[edge_index])
                    for edge_id in candidates:
                        other_edge = right.edges[int(edge_id)]
                        radius = clearance + radius_a + float(right.edge_half_lengths[int(edge_id)])
                        if float(np.linalg.norm(center - right.edge_centers[int(edge_id)])) > radius:
                            continue
                        edge_b = (int(other_edge[0]), int(other_edge[1]))
                        point_a, point_b, _factor_a, _factor_b = _closest_points_on_segments(
                            current[edge_a[0]],
                            current[edge_a[1]],
                            current[edge_b[0]],
                            current[edge_b[1]],
                        )
                        fallback = _canonical_direction(
                            np.cross(
                                current[edge_a[1]] - current[edge_a[0]],
                                current[edge_b[1]] - current[edge_b[0]],
                            )
                            if float(np.linalg.norm(np.cross(
                                current[edge_a[1]] - current[edge_a[0]],
                                current[edge_b[1]] - current[edge_b[0]],
                            ))) > 1e-12
                            else np.cross(
                                current[edge_a[1]] - current[edge_a[0]],
                                np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
                                if abs(float(current[edge_a[1], 0] - current[edge_a[0], 0])) < 0.9
                                else np.asarray((0.0, 1.0, 0.0), dtype=np.float64),
                            )
                        )
                        contact, penetration = _accumulate_edge_edge(
                            current,
                            edge_a,
                            edge_b,
                            masses,
                            clearance,
                            fallback,
                            correction_sum,
                            correction_count,
                        )
                        contacts_this_pass += int(contact)
                        max_penetration_this_pass = max(
                            max_penetration_this_pass,
                            penetration if contact else 0.0,
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
        correction_directions[moved] = corrections[moved]
        if _iteration == 0:
            contacts_before = contacts_this_pass
            max_penetration_before = max_penetration_this_pass
        if not bool(np.any(moved)):
            break

    remaining_contacts, max_penetration_after = _candidate_contact_statistics(
        current,
        surfaces,
        clearance,
    )
    movement = np.linalg.norm(current - original, axis=1)
    corrected_count = int(np.count_nonzero(movement > 1e-8))
    correction_lengths = np.linalg.norm(correction_directions, axis=1)
    nonzero = correction_lengths > 1e-10
    correction_directions[nonzero] /= correction_lengths[nonzero, None]
    correction_directions[~nonzero] = 0.0
    metrics = InterClothContactMetrics(
        contacts_before,
        corrected_count,
        remaining_contacts,
        max_penetration_before,
        max_penetration_after,
    )
    return current, correction_directions, metrics

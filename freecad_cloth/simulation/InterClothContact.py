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
        sys.stdout.write(f"{message}\n")
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
    triangle_minimums: PointArray
    triangle_maximums: PointArray
    triangle_tree: KDTree
    edges: EdgeArray
    edge_centers: PointArray
    edge_half_lengths: PointArray
    edge_minimums: PointArray
    edge_maximums: PointArray
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


def _barycentric_coordinates_batch(
    points: PointArray,
    triangles: PointArray,
) -> PointArray:
    """Return barycentric coordinates for paired points and triangle planes."""
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    ab = b - a
    ac = c - a
    ap = points - a
    d00 = np.einsum("ij,ij->i", ab, ab)
    d01 = np.einsum("ij,ij->i", ab, ac)
    d11 = np.einsum("ij,ij->i", ac, ac)
    d20 = np.einsum("ij,ij->i", ap, ab)
    d21 = np.einsum("ij,ij->i", ap, ac)
    denominator = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    return np.column_stack((1.0 - v - w, v, w))


def _closest_points_to_triangles_batch(
    points: PointArray,
    triangles: PointArray,
) -> tuple[PointArray, PointArray, PointArray]:
    """Return exact point/triangle closest geometry for a batch of paired faces."""
    barycentric = _barycentric_coordinates_batch(points, triangles)
    inside = np.all(barycentric >= 0.0, axis=1)
    closest = np.einsum("ni,nij->nj", barycentric, triangles)
    weights = barycentric.copy()
    difference = points - closest
    distance_squared = np.einsum("ij,ij->i", difference, difference)
    distance_squared[~inside] = np.inf

    for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
        start = triangles[:, start_index]
        direction = triangles[:, end_index] - start
        length_squared = np.einsum("ij,ij->i", direction, direction)
        numerator = np.einsum("ij,ij->i", points - start, direction)
        factor = np.clip(numerator / length_squared, 0.0, 1.0)
        candidate = start + factor[:, None] * direction
        delta = points - candidate
        candidate_distance_squared = np.einsum("ij,ij->i", delta, delta)
        better = (~inside) & (candidate_distance_squared < distance_squared)
        closest[better] = candidate[better]
        distance_squared[better] = candidate_distance_squared[better]
        weights[better] = 0.0
        weights[better, start_index] = 1.0 - factor[better]
        weights[better, end_index] = factor[better]

    return closest, weights, distance_squared


def _closest_segments_batch(
    first_start: PointArray,
    first_end: PointArray,
    second_start: PointArray,
    second_end: PointArray,
) -> tuple[PointArray, PointArray, PointArray, PointArray]:
    """Return closest points and interpolation factors for paired segment batches."""
    first_direction = first_end - first_start
    second_direction = second_end - second_start
    relative = first_start - second_start
    first_squared = np.einsum("ij,ij->i", first_direction, first_direction)
    second_squared = np.einsum("ij,ij->i", second_direction, second_direction)
    directions_dot = np.einsum("ij,ij->i", first_direction, second_direction)
    first_relative = np.einsum("ij,ij->i", first_direction, relative)
    second_relative = np.einsum("ij,ij->i", second_direction, relative)
    epsilon = 1e-18

    denominator = first_squared * second_squared - directions_dot * directions_dot
    first_factor = np.divide(
        directions_dot * second_relative - first_relative * second_squared,
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > epsilon,
    )
    first_factor = np.clip(first_factor, 0.0, 1.0)
    second_factor = np.divide(
        directions_dot * first_factor + second_relative,
        second_squared,
        out=np.zeros_like(second_squared),
        where=second_squared > epsilon,
    )
    below = second_factor < 0.0
    above = second_factor > 1.0
    second_factor = np.clip(second_factor, 0.0, 1.0)
    safe_first_squared = np.maximum(first_squared, epsilon)
    first_factor = np.where(
        below,
        np.clip(-first_relative / safe_first_squared, 0.0, 1.0),
        first_factor,
    )
    first_factor = np.where(
        above,
        np.clip((directions_dot - first_relative) / safe_first_squared, 0.0, 1.0),
        first_factor,
    )

    first_degenerate = first_squared <= epsilon
    second_degenerate = second_squared <= epsilon
    both_degenerate = first_degenerate & second_degenerate
    first_factor = np.where(first_degenerate, 0.0, first_factor)
    second_factor = np.where(second_degenerate, 0.0, second_factor)
    second_factor = np.where(
        first_degenerate & ~second_degenerate,
        np.clip(
            second_relative / np.maximum(second_squared, epsilon),
            0.0,
            1.0,
        ),
        second_factor,
    )
    first_factor = np.where(
        second_degenerate & ~first_degenerate,
        np.clip(-first_relative / safe_first_squared, 0.0, 1.0),
        first_factor,
    )
    first_factor = np.where(both_degenerate, 0.0, first_factor)
    second_factor = np.where(both_degenerate, 0.0, second_factor)

    first_point = first_start + first_factor[:, None] * first_direction
    second_point = second_start + second_factor[:, None] * second_direction
    return first_point, second_point, first_factor, second_factor


def _closest_segment_triangles_batch(
    starts: PointArray,
    ends: PointArray,
    triangles: PointArray,
) -> tuple[PointArray, PointArray, PointArray, PointArray, PointArray, PointArray]:
    """Compute exact segment/triangle closest geometry without per-pair Python calls.

    The candidate list is already conservatively bounded by the surface index.
    Vectorized face, endpoint and edge tests preserve the scalar narrow-phase
    definition while moving its arithmetic into NumPy's compiled kernels.
    """
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    ab = b - a
    ac = c - a
    cross = np.cross(ab, ac)
    normal_lengths = np.linalg.norm(cross, axis=1)
    normals = cross / normal_lengths[:, None]
    direction = ends - starts
    signed_start = np.einsum("ij,ij->i", starts - a, normals)
    signed_delta = np.einsum("ij,ij->i", direction, normals)
    valid_plane_intersection = np.abs(signed_delta) > 1e-12
    intersection_factor = np.divide(
        -signed_start,
        signed_delta,
        out=np.zeros_like(signed_start),
        where=valid_plane_intersection,
    )
    intersection_point = starts + intersection_factor[:, None] * direction
    intersection_weights = _barycentric_coordinates_batch(intersection_point, triangles)
    intersects_face = (
        valid_plane_intersection
        & (intersection_factor >= 0.0)
        & (intersection_factor <= 1.0)
        & (np.min(intersection_weights, axis=1) >= -1e-10)
    )

    count = len(starts)
    best_distance_squared = np.full(count, np.inf, dtype=np.float64)
    best_edge_points = np.empty((count, 3), dtype=np.float64)
    best_face_points = np.empty((count, 3), dtype=np.float64)
    best_edge_factors = np.zeros(count, dtype=np.float64)
    best_face_weights = np.zeros((count, 3), dtype=np.float64)

    if bool(np.any(intersects_face)):
        weights = np.maximum(intersection_weights[intersects_face], 0.0)
        weights /= np.sum(weights, axis=1)[:, None]
        best_distance_squared[intersects_face] = 0.0
        best_edge_points[intersects_face] = intersection_point[intersects_face]
        best_face_points[intersects_face] = intersection_point[intersects_face]
        best_edge_factors[intersects_face] = intersection_factor[intersects_face]
        best_face_weights[intersects_face] = weights

    projection_factor = np.where(
        valid_plane_intersection,
        np.clip(intersection_factor, 0.0, 1.0),
        0.5,
    )
    projected_edge_points = starts + projection_factor[:, None] * direction
    projected_face_points = projected_edge_points - (
        np.einsum("ij,ij->i", projected_edge_points - a, normals)[:, None] * normals
    )
    projected_weights = _barycentric_coordinates_batch(projected_face_points, triangles)
    projected_inside = np.min(projected_weights, axis=1) >= -1e-10
    projected_weights = np.maximum(projected_weights, 0.0)
    projected_weights /= np.sum(projected_weights, axis=1)[:, None]
    projected_delta = projected_edge_points - projected_face_points
    projected_distance_squared = np.einsum("ij,ij->i", projected_delta, projected_delta)
    better = projected_inside & (projected_distance_squared < best_distance_squared)
    best_distance_squared[better] = projected_distance_squared[better]
    best_edge_points[better] = projected_edge_points[better]
    best_face_points[better] = projected_face_points[better]
    best_edge_factors[better] = projection_factor[better]
    best_face_weights[better] = projected_weights[better]

    for factor, endpoint in ((0.0, starts), (1.0, ends)):
        face_points, face_weights, distance_squared = _closest_points_to_triangles_batch(
            endpoint,
            triangles,
        )
        better = distance_squared < best_distance_squared
        best_distance_squared[better] = distance_squared[better]
        best_edge_points[better] = endpoint[better]
        best_face_points[better] = face_points[better]
        best_edge_factors[better] = factor
        best_face_weights[better] = face_weights[better]

    for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
        edge_points, face_points, edge_factors, face_factors = _closest_segments_batch(
            starts,
            ends,
            triangles[:, start_index],
            triangles[:, end_index],
        )
        difference = edge_points - face_points
        distance_squared = np.einsum("ij,ij->i", difference, difference)
        better = distance_squared < best_distance_squared
        face_weights = np.zeros((count, 3), dtype=np.float64)
        face_weights[:, start_index] = 1.0 - face_factors
        face_weights[:, end_index] = face_factors
        best_distance_squared[better] = distance_squared[better]
        best_edge_points[better] = edge_points[better]
        best_face_points[better] = face_points[better]
        best_edge_factors[better] = edge_factors[better]
        best_face_weights[better] = face_weights[better]

    return (
        best_edge_points,
        best_face_points,
        best_edge_factors,
        best_face_weights,
        normals,
        best_distance_squared,
    )


def _candidate_edge_triangle_pairs(
    source: _SurfaceIndex,
    target: _SurfaceIndex,
    clearance_mm: float,
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64], int, float, float]:
    """Batch conservative edge/triangle broad-phase queries for one direction."""
    radii = clearance_mm + source.edge_half_lengths + float(target.triangle_radii.max())
    query_started = time.perf_counter()
    neighbors = target.triangle_tree.query_ball_point(
        source.edge_centers,
        radii,
        return_sorted=True,
    )
    query_seconds = time.perf_counter() - query_started
    counts = np.fromiter(
        (len(indices) for indices in neighbors),
        dtype=np.int64,
        count=len(source.edges),
    )
    candidate_count = int(np.sum(counts))
    if candidate_count == 0:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty.copy(), 0, query_seconds, 0.0

    source_edge_indices = np.repeat(
        np.arange(len(source.edges), dtype=np.int64),
        counts,
    )
    target_triangle_indices = np.concatenate(
        [np.asarray(indices, dtype=np.int64) for indices in neighbors if len(indices)]
    )
    filter_started = time.perf_counter()
    # An expanded segment AABB and triangle AABB are a conservative distance
    # broad phase: any pair within the requested Euclidean clearance must overlap
    # on all three axes. This is substantially tighter than centre/radius spheres
    # for long, thin cloth triangles and avoids expensive exact tests for them.
    edge_minimums = source.edge_minimums[source_edge_indices] - clearance_mm
    edge_maximums = source.edge_maximums[source_edge_indices] + clearance_mm
    triangle_minimums = target.triangle_minimums[target_triangle_indices]
    triangle_maximums = target.triangle_maximums[target_triangle_indices]
    plausible = np.all(
        (edge_maximums >= triangle_minimums)
        & (triangle_maximums >= edge_minimums),
        axis=1,
    )
    source_edge_indices = source_edge_indices[plausible]
    target_triangle_indices = target_triangle_indices[plausible]
    filter_seconds = time.perf_counter() - filter_started
    return (
        source_edge_indices,
        target_triangle_indices,
        candidate_count,
        query_seconds,
        filter_seconds,
    )


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
    triangle_minimums = triangle_points.min(axis=1)
    triangle_maximums = triangle_points.max(axis=1)
    triangle_tree = KDTree(triangle_centers)

    directed_edges = np.concatenate(
        (triangles[:, (0, 1)], triangles[:, (1, 2)], triangles[:, (2, 0)]),
        axis=0,
    )
    edges = np.unique(np.sort(directed_edges, axis=1), axis=0)
    edge_points = positions[edges]
    edge_centers = edge_points.mean(axis=1)
    edge_half_lengths = np.linalg.norm(edge_points[:, 1] - edge_points[:, 0], axis=1) * 0.5
    edge_minimums = edge_points.min(axis=1)
    edge_maximums = edge_points.max(axis=1)
    edge_tree = KDTree(edge_centers)
    return _SurfaceIndex(
        triangles,
        triangle_centers,
        triangle_radii,
        triangle_minimums,
        triangle_maximums,
        triangle_tree,
        edges,
        edge_centers,
        edge_half_lengths,
        edge_minimums,
        edge_maximums,
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
    closest_geometry: tuple[PointArray, PointArray, float, PointArray, PointArray] | None = None,
) -> tuple[bool, float]:
    """Accumulate one two-sided edge/triangle separation constraint."""
    source_ids = np.asarray(source_edge, dtype=np.int64)
    target_ids = np.asarray(target_triangle, dtype=np.int64)
    if closest_geometry is None:
        closest_geometry = _closest_segment_triangle(
            positions[source_ids[0]],
            positions[source_ids[1]],
            positions[target_ids],
        )
    edge_point, face_point, factor, face_weights, normal = closest_geometry
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
    measurement_started = time.perf_counter()
    measured_candidates = 0
    exact_tests = 0
    query_seconds = 0.0
    filter_seconds = 0.0
    closest_seconds = 0.0

    for left_index, left_id in enumerate(group_ids):
        left = surfaces[left_id]
        for right_id in group_ids[left_index + 1 :]:
            right = surfaces[right_id]
            for source, target in ((left, right), (right, left)):
                (
                    source_edge_indices,
                    target_triangle_indices,
                    _raw_candidate_count,
                    query_elapsed,
                    filter_elapsed,
                ) = _candidate_edge_triangle_pairs(source, target, clearance_mm)
                query_seconds += query_elapsed
                filter_seconds += filter_elapsed
                if source_edge_indices.size == 0:
                    continue

                closest_started = time.perf_counter()
                _edge_points, _face_points, _factors, _weights, _normals, distances_squared = (
                    _closest_segment_triangles_batch(
                        positions[source.edges[source_edge_indices, 0]],
                        positions[source.edges[source_edge_indices, 1]],
                        positions[target.triangles[target_triangle_indices]],
                    )
                )
                closest_seconds += time.perf_counter() - closest_started
                candidate_count = len(source_edge_indices)
                measured_candidates += candidate_count
                exact_tests += candidate_count
                # Use the batch distance from the exact segment/triangle narrow phase.
                penetration = clearance_mm - np.sqrt(distances_squared)
                residual = penetration > _CONTACT_MEASUREMENT_EPSILON_MM
                residual_count = int(np.count_nonzero(residual))
                contact_count += residual_count
                if residual_count:
                    maximum = max(maximum, float(np.max(penetration[residual])))

    _emit_contact_diagnostic(
        f"inter-cloth-measure-finish candidates={measured_candidates} exact_tests={exact_tests} "
        f"query_s={query_seconds:.2f} filter_s={filter_seconds:.2f} "
        f"closest_s={closest_seconds:.2f} elapsed_s={time.perf_counter() - measurement_started:.2f}"
    )
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
    measure_residual: bool = True,
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
        index_elapsed = 0.0
        if iteration > 0:
            index_started = time.perf_counter()
            surfaces = {
                group_id: _surface_index(current, surface.triangles)
                for group_id, surface in surfaces.items()
            }
            index_elapsed = time.perf_counter() - index_started
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
                    _emit_contact_diagnostic(
                        f"inter-cloth-direction-start iteration={iteration + 1} "
                        f"source_edges={len(source.edges)} target_triangles={len(target.triangles)} "
                        f"direction={direction_index}"
                    )
                    source_center = current[np.unique(source.triangles)].mean(axis=0)
                    target_center = current[np.unique(target.triangles)].mean(axis=0)
                    (
                        source_edge_indices,
                        target_triangle_indices,
                        candidate_count,
                        query_seconds,
                        filter_seconds,
                    ) = _candidate_edge_triangle_pairs(source, target, clearance)
                    plausible_candidate_count = len(source_edge_indices)
                    exact_tests = plausible_candidate_count
                    closest_started = time.perf_counter()
                    if plausible_candidate_count:
                        (
                            edge_points,
                            face_points,
                            edge_factors,
                            face_weights,
                            normals,
                            distances_squared,
                        ) = _closest_segment_triangles_batch(
                            current[source.edges[source_edge_indices, 0]],
                            current[source.edges[source_edge_indices, 1]],
                            current[target.triangles[target_triangle_indices]],
                        )
                    else:
                        edge_points = np.empty((0, 3), dtype=np.float64)
                        face_points = np.empty((0, 3), dtype=np.float64)
                        edge_factors = np.empty(0, dtype=np.float64)
                        face_weights = np.empty((0, 3), dtype=np.float64)
                        normals = np.empty((0, 3), dtype=np.float64)
                        distances_squared = np.empty(0, dtype=np.float64)
                    closest_seconds = time.perf_counter() - closest_started

                    correction_started = time.perf_counter()
                    active_constraints = 0
                    if plausible_candidate_count:
                        best_distance_by_edge = np.full(
                            len(source.edges),
                            np.inf,
                            dtype=np.float64,
                        )
                        np.minimum.at(
                            best_distance_by_edge,
                            source_edge_indices,
                            distances_squared,
                        )
                        is_nearest = distances_squared == best_distance_by_edge[source_edge_indices]
                        best_triangle_by_edge = np.full(
                            len(source.edges),
                            np.iinfo(np.int64).max,
                            dtype=np.int64,
                        )
                        np.minimum.at(
                            best_triangle_by_edge,
                            source_edge_indices[is_nearest],
                            target_triangle_indices[is_nearest],
                        )
                        selected_positions = np.flatnonzero(
                            is_nearest
                            & (
                                target_triangle_indices
                                == best_triangle_by_edge[source_edge_indices]
                            )
                            & (distances_squared < clearance * clearance)
                        )
                        for candidate_position in selected_positions:
                            edge_index = int(source_edge_indices[candidate_position])
                            triangle_index = int(target_triangle_indices[candidate_position])
                            edge = source.edges[edge_index]
                            triangle_values = target.triangles[triangle_index]
                            triangle: tuple[int, int, int] = (
                                int(triangle_values[0]),
                                int(triangle_values[1]),
                                int(triangle_values[2]),
                            )
                            closest_geometry = (
                                edge_points[candidate_position],
                                face_points[candidate_position],
                                float(edge_factors[candidate_position]),
                                face_weights[candidate_position],
                                normals[candidate_position],
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
                                closest_geometry=closest_geometry,
                            )
                            active_constraints += int(contact)
                            contacts_this_pass += int(contact)
                            maximum_this_pass = max(
                                maximum_this_pass,
                                penetration if contact else 0.0,
                            )
                    correction_seconds = time.perf_counter() - correction_started
                    _emit_contact_diagnostic(
                        f"inter-cloth-direction-finish iteration={iteration + 1} "
                        f"direction={direction_index} candidates={candidate_count} "
                        f"plausible={plausible_candidate_count} exact_tests={exact_tests} "
                        f"active_constraints={active_constraints} query_s={query_seconds:.2f} "
                        f"filter_s={filter_seconds:.2f} closest_s={closest_seconds:.2f} "
                        f"correction_s={correction_seconds:.2f} "
                        f"elapsed_s={time.perf_counter() - direction_started:.2f}"
                    )

        # Jacobi accumulation can produce several compatible corrections for
        # one particle. Averaging all of them by contact count over-damps dense
        # cloth regions and leaves visible clearance deficits after the bounded
        # pass budget. Sum the independent corrections, but cap each particle's
        # displacement to one requested clearance to prevent a dense contact
        # fan from producing an unbounded jump.
        corrections = correction_sum.copy()
        correction_lengths = np.linalg.norm(corrections, axis=1)
        correction_scales = np.minimum(
            1.0,
            clearance / np.maximum(correction_lengths, 1e-12),
        )
        corrections *= correction_scales[:, None]
        _share_sewn_corrections(corrections, masses, clusters)
        moved = np.linalg.norm(corrections, axis=1) > 1e-10
        current += alpha * corrections
        if iteration == 0:
            contacts_before = contacts_this_pass
            maximum_before = maximum_this_pass
        _emit_contact_diagnostic(
            f"inter-cloth-pass-finish iteration={iteration + 1} "
            f"contacts={contacts_this_pass} moved={int(np.count_nonzero(moved))} "
            f"index_s={index_elapsed:.2f} elapsed_s={time.perf_counter() - pass_started:.1f}"
        )
        if not bool(np.any(moved)):
            break

    remaining_contacts = 0
    maximum_after = 0.0
    if measure_residual:
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

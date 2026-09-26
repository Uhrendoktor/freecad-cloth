"""Deterministic authored-surface containment for the optional Tissu backend.

The index is built from the full authored collision mesh and is independent of
the solver-facing collision decimation.  It provides two operations used only by
an explicit Tissu experiment flag:

* parity-based inside/outside classification against a closed triangle mesh;
* nearest authored surface point plus an outward normal for projection.

The implementation is FreeCAD-independent so the geometry contract can be
unit-tested without the GUI or the optional Tissu wheel.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


_RAY_DIRECTION = np.asarray((1.0, 0.3713906763541037, 0.2178285360995444), dtype=np.float64)
_RAY_DIRECTION /= np.linalg.norm(_RAY_DIRECTION)
_DEFAULT_LEAF_SIZE = 16
_BOUNDARY_EPSILON = 1.0e-8


def _point_aabb_distance_sq(point, minimum, maximum):
    delta = np.maximum(np.maximum(minimum - point, 0.0), point - maximum)
    return float(np.dot(delta, delta))


def _closest_point_on_triangle(point, a, b, c):
    ab = b - a
    ac = c - a
    ap = point - a
    d1 = float(np.dot(ab, ap))
    d2 = float(np.dot(ac, ap))
    if d1 <= 0.0 and d2 <= 0.0:
        return a

    bp = point - b
    d3 = float(np.dot(ab, bp))
    d4 = float(np.dot(ac, bp))
    if d3 >= 0.0 and d4 <= d3:
        return b

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        value = d1 / max(d1 - d3, 1.0e-30)
        return a + value * ab

    cp = point - c
    d5 = float(np.dot(ab, cp))
    d6 = float(np.dot(ac, cp))
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        value = d2 / max(d2 - d6, 1.0e-30)
        return a + value * ac

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        value = (d4 - d3) / max((d4 - d3) + (d5 - d6), 1.0e-30)
        return b + value * (c - b)

    denominator = max(va + vb + vc, 1.0e-30)
    v = vb / denominator
    w = vc / denominator
    return a + ab * v + ac * w


def _ray_intersects_triangle(point, direction, a, b, c):
    edge1 = b - a
    edge2 = c - a
    pvec = np.cross(direction, edge2)
    determinant = float(np.dot(edge1, pvec))
    if abs(determinant) <= 1.0e-12:
        return False
    inv = 1.0 / determinant
    tvec = point - a
    u = float(np.dot(tvec, pvec)) * inv
    if u < -1.0e-10 or u > 1.0 + 1.0e-10:
        return False
    qvec = np.cross(tvec, edge1)
    v = float(np.dot(direction, qvec)) * inv
    if v < -1.0e-10 or u + v > 1.0 + 1.0e-10:
        return False
    distance = float(np.dot(edge2, qvec)) * inv
    return distance > _BOUNDARY_EPSILON


def _ray_intersects_aabb(point, direction, minimum, maximum):
    inverse = np.empty(3, dtype=np.float64)
    origin = np.asarray(point, dtype=np.float64)
    for index in range(3):
        if abs(float(direction[index])) <= 1.0e-15:
            if origin[index] < minimum[index] or origin[index] > maximum[index]:
                return False
            inverse[index] = math.inf
        else:
            inverse[index] = 1.0 / float(direction[index])
    t1 = (minimum - origin) * inverse
    t2 = (maximum - origin) * inverse
    near = np.minimum(t1, t2)
    far = np.maximum(t1, t2)
    near_value = max(float(near[0]), float(near[1]), float(near[2]), 0.0)
    far_value = min(float(far[0]), float(far[1]), float(far[2]))
    return far_value >= near_value


@dataclass(frozen=True)
class _Node:
    minimum: np.ndarray
    maximum: np.ndarray
    left: int = -1
    right: int = -1
    start: int = 0
    end: int = 0


class AuthoredSurfaceIndex:
    """BVH index over a closed authored triangle surface."""

    def __init__(self, vertices, triangles, leaf_size=_DEFAULT_LEAF_SIZE):
        vertex_array = np.asarray(vertices, dtype=np.float64)
        triangle_array = np.asarray(triangles, dtype=np.int32)
        if vertex_array.ndim != 2 or vertex_array.shape[1] != 3:
            raise ValueError("authored containment vertices must be an Nx3 array")
        if triangle_array.ndim != 2 or triangle_array.shape[1] != 3 or not len(triangle_array):
            raise ValueError("authored containment triangles must be a non-empty Mx3 array")
        if int(np.min(triangle_array)) < 0 or int(np.max(triangle_array)) >= len(vertex_array):
            raise ValueError("authored containment triangle index out of range")
        if int(leaf_size) < 1:
            raise ValueError("authored containment leaf size must be positive")

        self.vertices = np.ascontiguousarray(vertex_array)
        self.triangles = np.ascontiguousarray(triangle_array)
        self._validate_closed_manifold()
        tri_vertices = self.vertices[self.triangles]
        self.triangle_min = np.min(tri_vertices, axis=1)
        self.triangle_max = np.max(tri_vertices, axis=1)
        self.centroids = (self.triangle_min + self.triangle_max) * 0.5

        raw_normals = np.cross(
            tri_vertices[:, 1] - tri_vertices[:, 0],
            tri_vertices[:, 2] - tri_vertices[:, 0],
        )
        normal_length = np.linalg.norm(raw_normals, axis=1)
        if np.any(normal_length <= 1.0e-14):
            raise ValueError("authored containment surface contains degenerate triangles")
        self.orientation_sign = 1.0 if self._signed_volume6() > 0.0 else -1.0
        self.normals = (
            raw_normals
            * self.orientation_sign
            / normal_length[:, None]
        )
        self.leaf_size = int(leaf_size)

        self._order = []
        self._nodes = []
        self._build(np.arange(len(self.triangles), dtype=np.int32))

    def _validate_closed_manifold(self):
        edges = {}
        for triangle_index, (a, b, c) in enumerate(self.triangles):
            for left, right in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
                key = (min(left, right), max(left, right))
                orientation = 1 if left < right else -1
                edges.setdefault(key, []).append((triangle_index, orientation))
        if any(len(uses) != 2 or uses[0][1] == uses[1][1] for uses in edges.values()):
            raise ValueError("authored containment surface must be closed and consistently wound")

    def _signed_volume6(self):
        tri_vertices = self.vertices[self.triangles]
        return float(
            np.sum(
                np.einsum(
                    "ij,ij->i",
                    tri_vertices[:, 0],
                    np.cross(tri_vertices[:, 1], tri_vertices[:, 2]),
                )
            )
        )

    def _build(self, triangle_ids):
        minimum = np.min(self.triangle_min[triangle_ids], axis=0)
        maximum = np.max(self.triangle_max[triangle_ids], axis=0)
        node_index = len(self._nodes)
        self._nodes.append(_Node(minimum, maximum))
        if len(triangle_ids) <= self.leaf_size:
            start = len(self._order)
            self._order.extend(int(value) for value in triangle_ids)
            end = len(self._order)
            self._nodes[node_index] = _Node(minimum, maximum, start=start, end=end)
            return node_index

        span = maximum - minimum
        axis = int(np.argmax(span))
        ordered = triangle_ids[np.argsort(self.centroids[triangle_ids, axis], kind="mergesort")]
        midpoint = len(ordered) // 2
        left = self._build(ordered[:midpoint])
        right = self._build(ordered[midpoint:])
        self._nodes[node_index] = _Node(minimum, maximum, left=left, right=right)
        return node_index

    def _nearest_triangle(self, point):
        point = np.asarray(point, dtype=np.float64)
        best_distance = math.inf
        best_triangle = -1
        best_point = None
        stack = [(0, 0.0)]
        while stack:
            node_index, bound = stack.pop()
            if bound > best_distance:
                continue
            node = self._nodes[node_index]
            if node.start != node.end:
                for order_index in range(node.start, node.end):
                    triangle_index = self._order[order_index]
                    a, b, c = self.vertices[self.triangles[triangle_index]]
                    candidate = _closest_point_on_triangle(point, a, b, c)
                    distance = float(np.dot(point - candidate, point - candidate))
                    if distance < best_distance:
                        best_distance = distance
                        best_triangle = triangle_index
                        best_point = candidate
                continue
            left = self._nodes[node.left]
            right = self._nodes[node.right]
            left_bound = _point_aabb_distance_sq(point, left.minimum, left.maximum)
            right_bound = _point_aabb_distance_sq(point, right.minimum, right.maximum)
            if left_bound <= right_bound:
                stack.append((node.right, right_bound))
                stack.append((node.left, left_bound))
            else:
                stack.append((node.left, left_bound))
                stack.append((node.right, right_bound))
        if best_triangle < 0:
            raise RuntimeError("authored containment nearest-surface query returned no triangle")
        return best_triangle, np.asarray(best_point, dtype=np.float64), best_distance

    def _parity_contains(self, point):
        stack = [0]
        intersections = 0
        while stack:
            node = self._nodes[stack.pop()]
            if not _ray_intersects_aabb(point, _RAY_DIRECTION, node.minimum, node.maximum):
                continue
            if node.start != node.end:
                for order_index in range(node.start, node.end):
                    triangle = self._order[order_index]
                    a, b, c = self.vertices[self.triangles[triangle]]
                    if _ray_intersects_triangle(point, _RAY_DIRECTION, a, b, c):
                        intersections += 1
                continue
            stack.append(node.left)
            stack.append(node.right)
        return (intersections % 2) == 1

    def contains(self, point, boundary_epsilon=_BOUNDARY_EPSILON):
        point = np.asarray(point, dtype=np.float64)
        _triangle_index, _closest, distance_sq = self._nearest_triangle(point)
        if distance_sq <= float(boundary_epsilon) ** 2:
            return False
        return self._parity_contains(point)

    def nearest(self, point):
        triangle_index, closest, distance_sq = self._nearest_triangle(point)
        return (
            closest,
            self.normals[triangle_index],
            math.sqrt(max(distance_sq, 0.0)),
        )

    def correction(self, point, thickness, boundary_epsilon=_BOUNDARY_EPSILON):
        point = np.asarray(point, dtype=np.float64)
        if not self._parity_contains(point):
            return None
        triangle_index, closest, distance_sq = self._nearest_triangle(point)
        if distance_sq <= float(boundary_epsilon) ** 2:
            return None
        normal = self.normals[triangle_index]
        distance = math.sqrt(max(distance_sq, 0.0))
        target = closest + normal * float(thickness)
        if float(np.dot(point - closest, normal)) > 1.0e-7:
            raise RuntimeError("authored containment normal points toward the inside")
        return target, float(distance)


def build_authored_surface_index(vertices, triangles, leaf_size=_DEFAULT_LEAF_SIZE):
    return AuthoredSurfaceIndex(vertices, triangles, leaf_size=leaf_size)

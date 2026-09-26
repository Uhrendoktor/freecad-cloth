"""Deterministic containment correction over an authored closed collision surface.

This module is intentionally FreeCAD- and solver-independent. The Tissu backend
uses it only when the explicit experimental environment gate is enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import floor, inf, sqrt
from weakref import WeakKeyDictionary

from freecad_cloth.avatar.AvatarCollision import CollisionSurface


_RAY_DIRECTION = (1.0, 0.2718281828, 0.1618033989)
_RAY_EPSILON = 1e-9
_TRIANGLE_EPSILON = 1e-12
_LEAF_SIZE = 8
_SURFACE_CACHE = WeakKeyDictionary()


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, factor):
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm_sq(a):
    return _dot(a, a)


def _normal(a, b, c):
    raw = _cross(_sub(b, a), _sub(c, a))
    length = sqrt(_norm_sq(raw))
    if length <= _TRIANGLE_EPSILON:
        return None
    return _scale(raw, 1.0 / length)


def _point_aabb_distance_sq(point, lower, upper):
    total = 0.0
    for index in range(3):
        value = float(point[index])
        if value < lower[index]:
            delta = lower[index] - value
        elif value > upper[index]:
            delta = value - upper[index]
        else:
            delta = 0.0
        total += delta * delta
    return total


def _ray_aabb_hit(origin, direction, lower, upper):
    t_min = 0.0
    t_max = inf
    for index in range(3):
        o = float(origin[index])
        d = float(direction[index])
        if abs(d) <= _RAY_EPSILON:
            if o < lower[index] or o > upper[index]:
                return False
            continue
        inv_d = 1.0 / d
        t0 = (lower[index] - o) * inv_d
        t1 = (upper[index] - o) * inv_d
        if t0 > t1:
            t0, t1 = t1, t0
        t_min = max(t_min, t0)
        t_max = min(t_max, t1)
        if t_max < t_min:
            return False
    return t_max >= max(t_min, _RAY_EPSILON)


def _ray_triangle_hit(origin, direction, a, b, c):
    edge1 = _sub(b, a)
    edge2 = _sub(c, a)
    pvec = _cross(direction, edge2)
    determinant = _dot(edge1, pvec)
    if abs(determinant) <= _RAY_EPSILON:
        return None
    inv_det = 1.0 / determinant
    tvec = _sub(origin, a)
    u = _dot(tvec, pvec) * inv_det
    if u <= _RAY_EPSILON or u >= 1.0 - _RAY_EPSILON:
        return None
    qvec = _cross(tvec, edge1)
    v = _dot(direction, qvec) * inv_det
    if v <= _RAY_EPSILON or u + v >= 1.0 - _RAY_EPSILON:
        return None
    distance = _dot(edge2, qvec) * inv_det
    if distance <= _RAY_EPSILON:
        return None
    return distance


def _closest_point_triangle(point, a, b, c):
    ab = _sub(b, a)
    ac = _sub(c, a)
    ap = _sub(point, a)
    d1 = _dot(ab, ap)
    d2 = _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a

    bp = _sub(point, b)
    d3 = _dot(ab, bp)
    d4 = _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        denominator = d1 - d3
        factor = d1 / denominator if abs(denominator) > _TRIANGLE_EPSILON else 0.0
        return _add(a, _scale(ab, factor))

    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denominator = d2 - d6
        factor = d2 / denominator if abs(denominator) > _TRIANGLE_EPSILON else 0.0
        return _add(a, _scale(ac, factor))

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        edge = _sub(c, b)
        denominator = (d4 - d3) + (d5 - d6)
        factor = (d4 - d3) / denominator if abs(denominator) > _TRIANGLE_EPSILON else 0.0
        return _add(b, _scale(edge, factor))

    denominator = va + vb + vc
    if abs(denominator) <= _TRIANGLE_EPSILON:
        return a
    denominator = 1.0 / denominator
    weight_b = vb * denominator
    weight_c = vc * denominator
    return _add(a, _add(_scale(ab, weight_b), _scale(ac, weight_c)))


@dataclass(frozen=True)
class _Triangle:
    index: int
    a: tuple[float, float, float]
    b: tuple[float, float, float]
    c: tuple[float, float, float]
    normal: tuple[float, float, float]
    lower: tuple[float, float, float]
    upper: tuple[float, float, float]
    centroid: tuple[float, float, float]


@dataclass(frozen=True)
class _Node:
    lower: tuple[float, float, float]
    upper: tuple[float, float, float]
    left: int | None = None
    right: int | None = None
    triangles: tuple[int, ...] = ()


class AuthoredSurfaceContainment:
    """Cached BVH, parity classifier, and outward-normal correction for a mesh."""

    def __init__(self, surface: CollisionSurface):
        surface.validate()
        if not surface.triangles:
            raise ValueError("containment surface needs triangles")

        edge_counts = {}
        winding = {}
        for a, b, c in surface.triangles:
            triangle = (int(a), int(b), int(c))
            for left, right in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
                edge = (min(left, right), max(left, right))
                orientation = 1 if left < right else -1
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
                winding[edge] = winding.get(edge, 0) + orientation
        invalid_edges = [
            edge for edge, count in edge_counts.items()
            if count != 2 or winding.get(edge, 0) != 0
        ]
        if invalid_edges:
            raise ValueError("authored containment surface must be closed and consistently wound")

        prepared = []
        for index, (ia, ib, ic) in enumerate(surface.triangles):
            a = tuple(float(value) for value in surface.vertices[ia])
            b = tuple(float(value) for value in surface.vertices[ib])
            c = tuple(float(value) for value in surface.vertices[ic])
            normal = _normal(a, b, c)
            if normal is None:
                raise ValueError("authored containment surface contains a degenerate triangle")
            lower = tuple(min(a[i], b[i], c[i]) for i in range(3))
            upper = tuple(max(a[i], b[i], c[i]) for i in range(3))
            centroid = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
            prepared.append(_Triangle(index, a, b, c, normal, lower, upper, centroid))

        self.surface = surface
        self._triangles = tuple(prepared)
        self._nodes: list[_Node] = []
        self._root = self._build(tuple(range(len(prepared))))

    def _build(self, indices):
        lower = tuple(min(self._triangles[index].lower[axis] for index in indices) for axis in range(3))
        upper = tuple(max(self._triangles[index].upper[axis] for index in indices) for axis in range(3))
        if len(indices) <= _LEAF_SIZE:
            node_id = len(self._nodes)
            self._nodes.append(_Node(lower, upper, triangles=tuple(sorted(indices))))
            return node_id

        extents = tuple(upper[axis] - lower[axis] for axis in range(3))
        axis = max(range(3), key=lambda value: (extents[value], -value))
        ordered = tuple(
            sorted(
                indices,
                key=lambda index: (self._triangles[index].centroid[axis], self._triangles[index].index),
            )
        )
        midpoint = len(ordered) // 2
        node_id = len(self._nodes)
        self._nodes.append(_Node(lower, upper))
        left = self._build(ordered[:midpoint])
        right = self._build(ordered[midpoint:])
        self._nodes[node_id] = _Node(lower, upper, left=left, right=right)
        return node_id

    def contains(self, point):
        """Classify a point by deterministic odd/even ray parity."""
        origin = _add(point, _scale(_RAY_DIRECTION, 1e-8))
        stack = [self._root]
        intersections = 0
        while stack:
            node_id = stack.pop()
            node = self._nodes[node_id]
            if not _ray_aabb_hit(origin, _RAY_DIRECTION, node.lower, node.upper):
                continue
            if node.triangles:
                for triangle_index in node.triangles:
                    triangle = self._triangles[triangle_index]
                    if _ray_aabb_hit(origin, _RAY_DIRECTION, triangle.lower, triangle.upper):
                        if _ray_triangle_hit(origin, _RAY_DIRECTION, triangle.a, triangle.b, triangle.c) is not None:
                            intersections += 1
                continue
            children = [child for child in (node.left, node.right) if child is not None]
            children.sort(reverse=True)
            stack.extend(children)
        return intersections % 2 == 1

    def nearest_surface_point(self, point):
        """Return (point, outward_normal, squared_distance, triangle_index)."""
        root = self._nodes[self._root]
        queue = []
        heappush(queue, (_point_aabb_distance_sq(point, root.lower, root.upper), self._root))
        best_distance = inf
        best = None
        while queue:
            node_distance, node_id = heappop(queue)
            if node_distance > best_distance + 1e-12:
                continue
            node = self._nodes[node_id]
            if node.triangles:
                for triangle_index in node.triangles:
                    triangle = self._triangles[triangle_index]
                    lower_distance = _point_aabb_distance_sq(point, triangle.lower, triangle.upper)
                    if lower_distance > best_distance + 1e-12:
                        continue
                    closest = _closest_point_triangle(point, triangle.a, triangle.b, triangle.c)
                    delta = _sub(point, closest)
                    distance_sq = _norm_sq(delta)
                    candidate = (distance_sq, triangle.index, closest, triangle.normal)
                    if best is None or candidate[:2] < best[:2]:
                        best_distance = distance_sq
                        best = candidate
                continue
            for child_id in (node.left, node.right):
                if child_id is None:
                    continue
                child = self._nodes[child_id]
                child_distance = _point_aabb_distance_sq(point, child.lower, child.upper)
                if child_distance <= best_distance + 1e-12:
                    heappush(queue, (child_distance, child_id))
        if best is None:
            raise RuntimeError("authored containment surface has no nearest triangle")
        distance_sq, triangle_index, closest, normal = best
        return closest, normal, distance_sq, triangle_index

    def correct(self, point):
        """Return a corrected point when inside, otherwise None."""
        if not self.contains(point):
            return None
        closest, normal, _distance_sq, _triangle_index = self.nearest_surface_point(point)
        thickness = max(0.0, float(self.surface.thickness))
        return _add(closest, _scale(normal, thickness))


def get_authored_surface_containment(surface: CollisionSurface):
    """Return the cached acceleration for an immutable authored collision surface."""
    cached = _SURFACE_CACHE.get(surface)
    if cached is None:
        cached = AuthoredSurfaceContainment(surface)
        _SURFACE_CACHE[surface] = cached
    return cached


def clear_authored_surface_containment_cache():
    """Clear derived acceleration state; the authoritative target is untouched."""
    _SURFACE_CACHE.clear()

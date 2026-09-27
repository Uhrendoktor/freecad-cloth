"""Deterministic solver-neutral target placement geometry helpers.

This module intentionally has no FreeCAD dependency. It operates on the small
CollisionSurface contract already used by the fitting and simulation layers.
"""

from dataclasses import dataclass
from heapq import heappop, heappush
from math import sqrt
import weakref


DEFAULT_SURFACE_CLEARANCE = 8.0
DEFAULT_MAX_TRANSLATION = 600.0
DEFAULT_AMBIGUITY_TOLERANCE = 1e-6


@dataclass(frozen=True)
class TargetSurfaceHit:
    triangle_index: int
    point: tuple[float, float, float]
    normal: tuple[float, float, float]
    distance: float


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale(a, factor):
    return tuple(float(a[i]) * float(factor) for i in range(3))


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _norm(a):
    return sqrt(max(0.0, _dot(a, a)))


def _unit(a, label):
    length = _norm(a)
    if length <= 1e-12:
        raise ValueError("%s must be non-zero" % label)
    return _scale(a, 1.0 / length)


def _closest_point_on_triangle(point, a, b, c):
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
        t = d1 / denominator if abs(denominator) > 1e-12 else 0.0
        return _add(a, _scale(ab, t))

    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denominator = d2 - d6
        t = d2 / denominator if abs(denominator) > 1e-12 else 0.0
        return _add(a, _scale(ac, t))

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        edge = _sub(c, b)
        denominator = (d4 - d3) + (d5 - d6)
        t = (d4 - d3) / denominator if denominator > 1e-12 else 0.0
        return _add(b, _scale(edge, t))

    denominator = va + vb + vc
    if abs(denominator) <= 1e-12:
        return a
    return _add(a, _add(_scale(ab, vb / denominator), _scale(ac, vc / denominator)))


def _surface_triangle_data(surface):
    surface.validate()
    vertices = tuple(tuple(float(value) for value in vertex) for vertex in surface.vertices)
    triangles = tuple(tuple(int(index) for index in triangle) for triangle in surface.triangles)
    if len(vertices) < 3 or not triangles:
        raise ValueError("target collision surface has no usable triangles")
    center = tuple(float(value) for value in surface.center)
    return vertices, triangles, center


def _outward_normal(a, b, c, center):
    normal = _unit(
        (
            (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
            (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
            (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
        ),
        "target surface triangle normal",
    )
    centroid = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
    outward = _sub(centroid, center)
    if _dot(normal, outward) < 0.0:
        normal = _scale(normal, -1.0)
    return normal


def _surface_is_closed_manifold(triangles):
    """Return whether the triangle topology is a closed 2-manifold.

    Each undirected edge must belong to exactly two triangles, and the
    incident triangle fan at every vertex must be connected through those
    shared edges. This rejects disconnected sheets that merely touch at a
    vertex and self-intersecting/non-manifold seams from using corner tie
    resolution.
    """
    edge_to_triangles = {}
    vertex_to_triangles = {}
    for triangle_index, triangle in enumerate(triangles):
        indices = tuple(int(index) for index in triangle)
        for vertex in indices:
            vertex_to_triangles.setdefault(vertex, set()).add(triangle_index)
        for index_a, index_b in ((indices[0], indices[1]), (indices[1], indices[2]), (indices[2], indices[0])):
            edge = tuple(sorted((index_a, index_b)))
            edge_to_triangles.setdefault(edge, set()).add(triangle_index)

    if not edge_to_triangles or any(len(items) != 2 for items in edge_to_triangles.values()):
        return False

    for vertex, incident in vertex_to_triangles.items():
        seed = next(iter(incident))
        connected = {seed}
        pending = [seed]
        while pending:
            triangle_index = pending.pop()
            triangle = triangles[triangle_index]
            for index_a, index_b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
                if vertex not in (index_a, index_b):
                    continue
                neighbours = edge_to_triangles.get(tuple(sorted((int(index_a), int(index_b)))), ())
                for neighbour in neighbours:
                    if neighbour not in connected:
                        connected.add(neighbour)
                        pending.append(neighbour)
        if connected != incident:
            return False

    return True


@dataclass(frozen=True)
class _TriangleRecord:
    triangle_index: int
    vertices: tuple[int, int, int]
    a: tuple[float, float, float]
    b: tuple[float, float, float]
    c: tuple[float, float, float]
    normal: tuple[float, float, float]
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    centroid: tuple[float, float, float]


@dataclass(frozen=True)
class _BvhNode:
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    left: int | None
    right: int | None
    triangles: tuple[int, ...]


class _SurfaceIndex:
    """Exact immutable BVH over one CollisionSurface geometry."""

    _LEAF_SIZE = 16

    def __init__(self, surface):
        vertices, triangles, center = _surface_triangle_data(surface)
        self._center = center
        self._closed_manifold = _surface_is_closed_manifold(triangles)
        self._records = []
        for triangle_index, triangle in enumerate(triangles):
            a, b, c = vertices[triangle[0]], vertices[triangle[1]], vertices[triangle[2]]
            try:
                normal = _outward_normal(a, b, c, center)
            except ValueError:
                continue
            self._records.append(
                _TriangleRecord(
                    triangle_index,
                    (int(triangle[0]), int(triangle[1]), int(triangle[2])),
                    a,
                    b,
                    c,
                    normal,
                    tuple(min(a[i], b[i], c[i]) for i in range(3)),
                    tuple(max(a[i], b[i], c[i]) for i in range(3)),
                    tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3)),
                )
            )
        if not self._records:
            raise ValueError("target collision surface contains no usable triangle normals")
        self._nodes = []
        self._root = self._build(tuple(range(len(self._records))))

    def _build(self, indices):
        node_id = len(self._nodes)
        self._nodes.append(None)
        minimum = tuple(
            min(self._records[index].minimum[axis] for index in indices)
            for axis in range(3)
        )
        maximum = tuple(
            max(self._records[index].maximum[axis] for index in indices)
            for axis in range(3)
        )
        if len(indices) <= self._LEAF_SIZE:
            self._nodes[node_id] = _BvhNode(minimum, maximum, None, None, tuple(indices))
            return node_id

        spans = tuple(maximum[axis] - minimum[axis] for axis in range(3))
        axis = max(range(3), key=lambda value: (spans[value], -value))
        ordered = sorted(
            indices,
            key=lambda index: (
                self._records[index].centroid[axis],
                self._records[index].triangle_index,
            ),
        )
        midpoint = len(ordered) // 2
        left = self._build(tuple(ordered[:midpoint]))
        right = self._build(tuple(ordered[midpoint:]))
        self._nodes[node_id] = _BvhNode(minimum, maximum, left, right, ())
        return node_id

    @staticmethod
    def _point_box_distance_sq(point, minimum, maximum):
        total = 0.0
        for axis in range(3):
            value = float(point[axis])
            if value < minimum[axis]:
                delta = minimum[axis] - value
                total += delta * delta
            elif value > maximum[axis]:
                delta = value - maximum[axis]
                total += delta * delta
        return total

    @staticmethod
    def _near_equal_triangles_are_local(candidate_vertices):
        if len(candidate_vertices) <= 1:
            return True
        connected = {0}
        pending = [0]
        vertex_sets = [set(vertices) for vertices in candidate_vertices]
        while pending:
            index = pending.pop()
            for other in range(len(candidate_vertices)):
                if other in connected:
                    continue
                if vertex_sets[index].intersection(vertex_sets[other]):
                    connected.add(other)
                    pending.append(other)
        return len(connected) == len(candidate_vertices)

    def nearest_hit(self, point, *, ambiguity_tolerance=DEFAULT_AMBIGUITY_TOLERANCE):
        point = tuple(float(value) for value in point)
        tolerance = float(ambiguity_tolerance)
        queue = [(0.0, self._root)]
        best = None
        evaluated = []
        candidate_count = 0

        while queue:
            lower_bound_sq, node_id = heappop(queue)
            if best is not None and lower_bound_sq > (best.distance + tolerance) ** 2:
                break
            node = self._nodes[node_id]
            if node.left is None:
                for record_index in node.triangles:
                    record = self._records[record_index]
                    closest = _closest_point_on_triangle(point, record.a, record.b, record.c)
                    distance = _norm(_sub(point, closest))
                    candidate_count += 1
                    hit = TargetSurfaceHit(record.triangle_index, closest, record.normal, distance)
                    evaluated.append((hit, record.vertices))
                    if (
                        best is None
                        or distance < best.distance
                        or (distance == best.distance and hit.triangle_index < best.triangle_index)
                    ):
                        best = hit
                continue

            left = self._nodes[node.left]
            right = self._nodes[node.right]
            heappush(queue, (self._point_box_distance_sq(point, left.minimum, left.maximum), node.left))
            heappush(queue, (self._point_box_distance_sq(point, right.minimum, right.maximum), node.right))

        if best is None:
            raise ValueError("target collision surface contains no usable triangle normals")

        near_equal = [
            (hit, vertices)
            for hit, vertices in evaluated
            if abs(hit.distance - best.distance) <= tolerance
        ]
        conflicts = [
            hit
            for hit, _vertices in near_equal
            if hit.triangle_index != best.triangle_index and _dot(hit.normal, best.normal) < -0.20
        ]
        if conflicts:
            raise ValueError("target snap anchor is ambiguous across surface normals")
        if len(near_equal) <= 1:
            return best, candidate_count

        # Preserve the historical deterministic behavior for coplanar or
        # otherwise closely aligned ties, including open surfaces. Only
        # materially different normals require manifold/topology proof.
        if all(
            _dot(hit.normal, best.normal) >= 0.20
            for hit, _vertices in near_equal
            if hit.triangle_index != best.triangle_index
        ):
            return best, candidate_count

        candidates = [hit for hit, _vertices in near_equal]
        candidate_vertices = [vertices for _hit, vertices in near_equal]
        if not self._closed_manifold or not self._near_equal_triangles_are_local(
            candidate_vertices
        ):
            raise ValueError("target snap anchor is ambiguous across surface normals")

        radial = _sub(point, self._center)
        if _norm(radial) > 1e-12:
            radial = _unit(radial, "target query direction")
            return min(
                candidates,
                key=lambda hit: (
                    -_dot(hit.normal, radial),
                    hit.triangle_index,
                ),
            ), candidate_count

        return min(candidates, key=lambda hit: hit.triangle_index), candidate_count

    def minimum_distance(self, point):
        point = tuple(float(value) for value in point)
        queue = [(0.0, self._root)]
        best_distance_sq = float("inf")
        while queue:
            lower_bound_sq, node_id = heappop(queue)
            if lower_bound_sq > best_distance_sq:
                break
            node = self._nodes[node_id]
            if node.left is None:
                for record_index in node.triangles:
                    record = self._records[record_index]
                    closest = _closest_point_on_triangle(point, record.a, record.b, record.c)
                    delta = _sub(point, closest)
                    best_distance_sq = min(best_distance_sq, _dot(delta, delta))
                continue
            left = self._nodes[node.left]
            right = self._nodes[node.right]
            heappush(queue, (self._point_box_distance_sq(point, left.minimum, left.maximum), node.left))
            heappush(queue, (self._point_box_distance_sq(point, right.minimum, right.maximum), node.right))
        if best_distance_sq == float("inf"):
            raise ValueError("target collision surface has no usable triangles")
        return sqrt(max(0.0, best_distance_sq))


_SURFACE_INDEX_CACHE = {}


def _surface_index(surface):
    key = id(surface)
    cached = _SURFACE_INDEX_CACHE.get(key)
    if cached is not None and cached[0]() is surface:
        return cached[1]
    index = _SurfaceIndex(surface)

    def _cleanup(ref, cache_key=key):
        current = _SURFACE_INDEX_CACHE.get(cache_key)
        if current is not None and current[0] is ref:
            _SURFACE_INDEX_CACHE.pop(cache_key, None)

    reference = weakref.ref(surface, _cleanup)
    _SURFACE_INDEX_CACHE[key] = (reference, index)
    return index


def _target_surface_query_candidate_count(surface, point):
    """Testing hook exposing deterministic BVH pruning without wall-clock gates."""
    return _surface_index(surface).nearest_hit(point)[1]


def target_surface_anchor(surface, point, *,
                           ambiguity_tolerance=DEFAULT_AMBIGUITY_TOLERANCE):
    """Return the nearest outward-facing surface point and normal.

    Coplanar/aligned ties keep deterministic nearest-triangle behavior.
    Materially different normals are resolved only on a verified local
    manifold fan; non-local or opposing ties remain fail-closed.
    """
    return _surface_index(surface).nearest_hit(
        point,
        ambiguity_tolerance=ambiguity_tolerance,
    )[0]


def translation_to_target(surface, centroid, *, clearance=DEFAULT_SURFACE_CLEARANCE,
                          max_translation=DEFAULT_MAX_TRANSLATION):
    """Return a single rigid translation that keeps piece spacing and rotations."""
    clearance = float(clearance)
    max_translation = float(max_translation)
    if clearance < 0.0:
        raise ValueError("target snap clearance must be non-negative")
    if max_translation <= 0.0:
        raise ValueError("target snap translation bound must be positive")
    hit = target_surface_anchor(surface, centroid)
    desired = _add(hit.point, _scale(hit.normal, clearance))
    delta = _sub(desired, centroid)
    distance = _norm(delta)
    if distance > max_translation + 1e-9:
        raise ValueError("target snap exceeds the configured translation bound")
    return delta, hit


def _ray_intersects_triangle(origin, direction, a, b, c, epsilon=1e-9):
    edge1 = _sub(b, a)
    edge2 = _sub(c, a)
    h = (
        direction[1] * edge2[2] - direction[2] * edge2[1],
        direction[2] * edge2[0] - direction[0] * edge2[2],
        direction[0] * edge2[1] - direction[1] * edge2[0],
    )
    determinant = _dot(edge1, h)
    if abs(determinant) <= epsilon:
        return False
    inverse = 1.0 / determinant
    s = _sub(origin, a)
    u = inverse * _dot(s, h)
    if u < -epsilon or u > 1.0 + epsilon:
        return False
    q = (
        s[1] * edge1[2] - s[2] * edge1[1],
        s[2] * edge1[0] - s[0] * edge1[2],
        s[0] * edge1[1] - s[1] * edge1[0],
    )
    v = inverse * _dot(direction, q)
    if v < -epsilon or u + v > 1.0 + epsilon:
        return False
    distance = inverse * _dot(edge2, q)
    return distance > epsilon


def _surface_is_closed(triangles):
    edges = {}
    for triangle in triangles:
        for index_a, index_b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            edge = tuple(sorted((int(index_a), int(index_b))))
            edges[edge] = edges.get(edge, 0) + 1
    return bool(edges) and all(count == 2 for count in edges.values())


def point_inside_closed_surface(surface, point):
    """Classify one point against a closed collision surface.

    Uses three deterministic oblique rays and majority parity, avoiding the
    O(particles * triangles) containment path that stalled the earlier probe.
    """
    vertices, triangles, _center = _surface_triangle_data(surface)
    if not _surface_is_closed(triangles):
        raise ValueError("target collision surface is not closed")
    point = tuple(float(value) for value in point)
    raw_directions = (
        (1.0, 0.371, 0.173),
        (0.271, 1.0, 0.411),
        (0.193, 0.311, 1.0),
    )
    classifications = []
    for raw in raw_directions:
        direction = _unit(raw, "ray direction")
        intersections = 0
        for triangle in triangles:
            if _ray_intersects_triangle(
                point,
                direction,
                vertices[triangle[0]],
                vertices[triangle[1]],
                vertices[triangle[2]],
            ):
                intersections += 1
        classifications.append(bool(intersections % 2))
    return sum(1 for value in classifications if value) >= 2


def nearest_surface_distance(surface, points):
    """Return the minimum unsigned point-to-surface distance."""
    index = _surface_index(surface)
    minimum = float("inf")
    for point in points:
        minimum = min(minimum, index.minimum_distance(point))
    return minimum


def minimum_outward_clearance(surface, points, *, tolerance=1e-6):
    """Return the minimum signed clearance along each nearest triangle normal.

    Positive values mean points lie on the outward side of their nearest
    local surface triangle; negative values are evidence of penetration.
    """
    index = _surface_index(surface)
    minimum = float("inf")
    for point in points:
        hit = index.nearest_hit(point)[0]
        signed = _dot(_sub(tuple(float(value) for value in point), hit.point), hit.normal)
        minimum = min(minimum, signed)
    if minimum < -float(tolerance):
        return minimum
    return max(0.0, minimum)


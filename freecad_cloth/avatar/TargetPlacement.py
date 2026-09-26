"""Deterministic, solver-neutral placement math against an authoritative collision surface."""
from dataclasses import dataclass
from math import sqrt, isfinite
from typing import Iterable, Tuple

Vector = Tuple[float, float, float]


def _vadd(a: Vector, b: Vector) -> Vector:
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _vsub(a: Vector, b: Vector) -> Vector:
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _vmul(a: Vector, scalar: float) -> Vector:
    return tuple(float(a[i]) * float(scalar) for i in range(3))


def _dot(a: Vector, b: Vector) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a: Vector, b: Vector) -> Vector:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(a: Vector) -> float:
    return sqrt(max(0.0, _dot(a, a)))


def _normalize(a: Vector) -> Vector:
    length = _norm(a)
    if length <= 1e-12:
        raise ValueError("target triangle normal is degenerate")
    return _vmul(a, 1.0 / length)


def _average(points: Iterable[Vector]) -> Vector:
    values = tuple(points)
    if not values:
        raise ValueError("at least one point is required")
    scale = 1.0 / len(values)
    return tuple(sum(float(point[i]) for point in values) * scale for i in range(3))


def _closest_point_on_triangle(point: Vector, a: Vector, b: Vector, c: Vector) -> Vector:
    ab = _vsub(b, a)
    ac = _vsub(c, a)
    ap = _vsub(point, a)
    d1 = _dot(ab, ap)
    d2 = _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = _vsub(point, b)
    d3 = _dot(ab, bp)
    d4 = _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        scale = d1 / max(1e-12, d1 - d3)
        return _vadd(a, _vmul(ab, scale))
    cp = _vsub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        scale = d2 / max(1e-12, d2 - d6)
        return _vadd(a, _vmul(ac, scale))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        scale = (d4 - d3) / max(1e-12, (d4 - d3) + (d5 - d6))
        return _vadd(b, _vmul(_vsub(c, b), scale))
    denominator = 1.0 / max(1e-12, va + vb + vc)
    return _vadd(a, _vadd(_vmul(ab, vb * denominator), _vmul(ac, vc * denominator)))


def _oriented_outward_normal(a: Vector, b: Vector, c: Vector, center: Vector) -> Vector:
    normal = _normalize(_cross(_vsub(b, a), _vsub(c, a)))
    triangle_center = _vmul(_vadd(_vadd(a, b), c), 1.0 / 3.0)
    if _dot(normal, _vsub(triangle_center, center)) < 0.0:
        normal = _vmul(normal, -1.0)
    return normal


@dataclass(frozen=True)
class _IndexedTriangle:
    index: int
    a: Vector
    b: Vector
    c: Vector
    normal: Vector
    minimum: Vector
    maximum: Vector


class _SurfaceIndex:
    def __init__(self, surface):
        surface.validate()
        self.minimum = tuple(
            min(float(vertex[axis]) for vertex in surface.vertices)
            for axis in range(3)
        )
        self.maximum = tuple(
            max(float(vertex[axis]) for vertex in surface.vertices)
            for axis in range(3)
        )
        self.center = surface.center
        triangle_count = len(surface.triangles)
        base_resolution = max(4, min(32, int(round(triangle_count ** (1.0 / 3.0))) * 2))
        extents = tuple(
            max(0.0, self.maximum[axis] - self.minimum[axis])
            for axis in range(3)
        )
        self.dimensions = tuple(
            base_resolution if extent > 1e-9 else 1
            for extent in extents
        )
        self.cell_size = tuple(
            (extents[axis] / self.dimensions[axis]) if extents[axis] > 1e-9 else 1.0
            for axis in range(3)
        )
        self.triangles = []
        self.buckets = {}
        for index, triangle in enumerate(surface.triangles):
            a, b, c = (surface.vertices[int(i)] for i in triangle)
            try:
                normal = _oriented_outward_normal(a, b, c, self.center)
            except ValueError:
                continue
            minimum = tuple(min(a[axis], b[axis], c[axis]) for axis in range(3))
            maximum = tuple(max(a[axis], b[axis], c[axis]) for axis in range(3))
            indexed = _IndexedTriangle(
                int(index),
                tuple(float(value) for value in a),
                tuple(float(value) for value in b),
                tuple(float(value) for value in c),
                normal,
                minimum,
                maximum,
            )
            local_index = len(self.triangles)
            self.triangles.append(indexed)
            ranges = []
            for axis in range(3):
                low = self._cell_index(minimum[axis], axis)
                high = self._cell_index(maximum[axis], axis)
                ranges.append(range(low, high + 1))
            for ix in ranges[0]:
                for iy in ranges[1]:
                    for iz in ranges[2]:
                        self.buckets.setdefault((ix, iy, iz), []).append(local_index)
        if not self.triangles:
            raise ValueError("target surface has no usable non-degenerate triangles")

    def _cell_index(self, value, axis):
        dimension = self.dimensions[axis]
        if dimension == 1:
            return 0
        scaled = (float(value) - self.minimum[axis]) / self.cell_size[axis]
        return max(0, min(dimension - 1, int(scaled)))

    def _cell_coords(self, point):
        return tuple(self._cell_index(point[axis], axis) for axis in range(3))

    def _shell_cells(self, base, radius):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy), abs(dz)) != radius:
                        continue
                    cell = (base[0] + dx, base[1] + dy, base[2] + dz)
                    if all(0 <= cell[axis] < self.dimensions[axis] for axis in range(3)):
                        yield cell

    def _unsearched_lower_bound(self, point, base, radius):
        lower_bound = float("inf")
        next_radius = radius + 1
        for axis in range(3):
            plus = base[axis] + next_radius
            if plus < self.dimensions[axis]:
                boundary = self.minimum[axis] + plus * self.cell_size[axis]
                lower_bound = min(lower_bound, max(0.0, boundary - point[axis]))
            minus = base[axis] - next_radius
            if minus >= 0:
                boundary = self.minimum[axis] + (minus + 1) * self.cell_size[axis]
                lower_bound = min(lower_bound, max(0.0, point[axis] - boundary))
        return lower_bound

    def nearest(self, point, ambiguity_tolerance):
        query = tuple(float(value) for value in point)
        base = self._cell_coords(query)
        best = None
        candidates = []
        seen = set()
        max_radius = max(self.dimensions)
        for radius in range(max_radius + 1):
            for cell in self._shell_cells(base, radius):
                for local_index in self.buckets.get(cell, ()):
                    if local_index in seen:
                        continue
                    seen.add(local_index)
                    triangle = self.triangles[local_index]
                    closest = _closest_point_on_triangle(query, triangle.a, triangle.b, triangle.c)
                    distance = _norm(_vsub(query, closest))
                    candidate = TargetProjection(
                        triangle.index,
                        closest,
                        triangle.normal,
                        distance,
                    )
                    if best is None or distance < best.distance - 1e-12:
                        best = candidate
                        candidates = [candidate]
                    elif abs(distance - best.distance) <= max(
                        float(ambiguity_tolerance),
                        best.distance * 1e-9,
                    ):
                        candidates.append(candidate)
            if best is not None:
                unseen_bound = self._unsearched_lower_bound(query, base, radius)
                if unseen_bound > best.distance + max(
                    float(ambiguity_tolerance),
                    best.distance * 1e-9,
                ):
                    break
            elif radius >= max_radius:
                break
        if best is None:
            raise ValueError("target surface has no usable non-degenerate triangles")
        for candidate in candidates[1:]:
            if _dot(candidate.normal, best.normal) < 0.5:
                raise ValueError("target projection is ambiguous across opposing surface normals")
        return best


_LAST_INDEX_SURFACE = None
_LAST_SURFACE_INDEX = None


def _surface_index(surface):
    global _LAST_INDEX_SURFACE, _LAST_SURFACE_INDEX
    if _LAST_INDEX_SURFACE is surface and _LAST_SURFACE_INDEX is not None:
        return _LAST_SURFACE_INDEX
    index = _SurfaceIndex(surface)
    _LAST_INDEX_SURFACE = surface
    _LAST_SURFACE_INDEX = index
    return index


@dataclass(frozen=True)
class TargetProjection:
    triangle_index: int
    point: Vector
    normal: Vector
    distance: float


def nearest_target_projection(point: Vector, surface, ambiguity_tolerance: float = 1e-6) -> TargetProjection:
    return _surface_index(surface).nearest(point, ambiguity_tolerance)


@dataclass(frozen=True)
class ClearanceReport:
    minimum_signed_clearance: float
    point_index: int
    point: Vector
    projection: TargetProjection


def minimum_signed_clearance(points: Iterable[Vector], surface) -> ClearanceReport:
    values = tuple(tuple(float(v) for v in point) for point in points)
    if not values:
        raise ValueError("clearance validation requires at least one garment sample point")
    best = None
    for index, point in enumerate(values):
        projection = nearest_target_projection(point, surface)
        signed = _dot(_vsub(point, projection.point), projection.normal)
        if not isfinite(signed):
            raise ValueError("target clearance became non-finite")
        report = ClearanceReport(signed, index, point, projection)
        if best is None or signed < best.minimum_signed_clearance:
            best = report
    return best


def average_point(points: Iterable[Vector]) -> Vector:
    return _average(points)

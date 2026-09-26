"""Deterministic, solver-neutral rigid garment placement against a target surface."""
from dataclasses import dataclass
from math import atan2, cos, degrees, floor, radians, sin, sqrt


class TargetPlacementError(ValueError):
    """Raised when target-aware placement cannot be proven safe."""


@dataclass(frozen=True)
class SurfaceHit:
    triangle_index: int
    point: tuple
    normal: tuple
    distance: float


@dataclass(frozen=True)
class RigidDelta:
    translation: tuple
    rotation_z: float
    residual_max: float


_WRAP_NORMALS = {
    "front": (0.0, 1.0, 0.0),
    "back": (0.0, -1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale(a, v):
    return tuple(float(a[i]) * float(v) for i in range(3))


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a):
    return sqrt(max(0.0, _dot(a, a)))


def _unit(a):
    length = _norm(a)
    if length <= 1e-12:
        raise TargetPlacementError("target surface contains a degenerate normal")
    return _scale(a, 1.0 / length)


def wrap_normal(wrap_direction):
    try:
        return _WRAP_NORMALS[str(wrap_direction)]
    except KeyError as exc:
        raise TargetPlacementError("unsupported garment wrap direction") from exc


def _surface_center(surface):
    return tuple(float(v) for v in surface.center)


def _triangle_data(surface, index, center=None):
    try:
        ia, ib, ic = surface.triangles[index]
        a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
    except (IndexError, TypeError, ValueError) as exc:
        raise TargetPlacementError("target surface triangle data is invalid") from exc
    if center is None:
        center = _surface_center(surface)
    normal = _unit(_cross(_sub(b, a), _sub(c, a)))
    triangle_center = _scale(_add(_add(a, b), c), 1.0 / 3.0)
    if _dot(normal, _sub(triangle_center, center)) < 0.0:
        normal = _scale(normal, -1.0)
    return tuple(a), tuple(b), tuple(c), normal


@dataclass(frozen=True)
class _TriangleRecord:
    a: tuple
    b: tuple
    c: tuple
    normal: tuple
    minimum: tuple
    maximum: tuple


class SurfaceSpatialIndex:
    """Exact nearest-surface queries without repeated whole-mesh recomputation."""

    def __init__(self, surface):
        vertices = tuple(getattr(surface, "vertices", ()) or ())
        triangles = tuple(getattr(surface, "triangles", ()) or ())
        if not vertices or not triangles:
            raise TargetPlacementError("target surface has no usable geometry")
        self.surface = surface
        self.center = _surface_center(surface)
        minimum = tuple(min(float(vertex[i]) for vertex in vertices) for i in range(3))
        maximum = tuple(max(float(vertex[i]) for vertex in vertices) for i in range(3))
        span = max(maximum[i] - minimum[i] for i in range(3))
        cells_per_axis = max(8, min(64, int(round(max(1, len(triangles)) ** (1.0 / 3.0)))))
        self.cell_size = max(20.0, span / float(cells_per_axis)) if span > 1e-9 else 20.0
        self.origin = minimum
        self._triangle_cells = {}
        self._vertex_cells = {}
        self.records = []
        self._build(triangles, vertices)

    def _cell_coord(self, point):
        return tuple(int(floor((float(point[i]) - self.origin[i]) / self.cell_size)) for i in range(3))

    def _cell_bounds(self, cell):
        low = tuple(self.origin[i] + float(cell[i]) * self.cell_size for i in range(3))
        high = tuple(low[i] + self.cell_size for i in range(3))
        return low, high

    def _cell_range(self, minimum, maximum):
        return self._cell_coord(minimum), self._cell_coord(maximum)

    def _build(self, triangles, vertices):
        for vertex_index, vertex in enumerate(vertices):
            self._vertex_cells.setdefault(self._cell_coord(vertex), []).append(vertex_index)
        for index, triangle in enumerate(triangles):
            a, b, c, normal = _triangle_data(self.surface, index, self.center)
            minimum = tuple(min(a[i], b[i], c[i]) for i in range(3))
            maximum = tuple(max(a[i], b[i], c[i]) for i in range(3))
            self.records.append(_TriangleRecord(a, b, c, normal, minimum, maximum))
            low, high = self._cell_range(minimum, maximum)
            for ix in range(low[0], high[0] + 1):
                for iy in range(low[1], high[1] + 1):
                    for iz in range(low[2], high[2] + 1):
                        self._triangle_cells.setdefault((ix, iy, iz), []).append(index)

    @staticmethod
    def _sort_hits(hits, limit):
        return tuple(sorted(hits, key=lambda item: (round(item.distance, 12), item.triangle_index))[:limit])

    def nearest_triangles(self, point, expected_normal=None, limit=1):
        expected = _unit(expected_normal) if expected_normal is not None else None
        center_cell = self._cell_coord(point)
        seen_cells = set()
        seen_triangles = set()
        best = []
        radius = 0
        while radius <= 128:
            low = tuple(center_cell[i] - radius for i in range(3))
            high = tuple(center_cell[i] + radius for i in range(3))
            for ix in range(low[0], high[0] + 1):
                for iy in range(low[1], high[1] + 1):
                    for iz in range(low[2], high[2] + 1):
                        cell = (ix, iy, iz)
                        if cell in seen_cells:
                            continue
                        seen_cells.add(cell)
                        for index in self._triangle_cells.get(cell, ()):
                            if index in seen_triangles:
                                continue
                            seen_triangles.add(index)
                            record = self.records[index]
                            if expected is not None and _dot(record.normal, expected) < 0.20:
                                continue
                            closest = _closest_point_on_triangle(point, record.a, record.b, record.c)
                            hit = SurfaceHit(
                                index,
                                closest,
                                record.normal,
                                _norm(_sub(point, closest)),
                            )
                            if len(best) < limit:
                                best.append(hit)
                                best = list(self._sort_hits(best, limit))
                            elif hit.distance < best[-1].distance:
                                best[-1] = hit
                                best = list(self._sort_hits(best, limit))
            if len(best) >= limit:
                cube_low = tuple(self.origin[i] + float(center_cell[i] - radius) * self.cell_size for i in range(3))
                cube_high = tuple(cube_low[i] + float(2 * radius + 1) * self.cell_size for i in range(3))
                lower_bound = min(
                    min(float(point[i]) - cube_low[i] for i in range(3)),
                    min(cube_high[i] - float(point[i]) for i in range(3)),
                )
                if best[-1].distance <= lower_bound + 1e-9:
                    break
            radius += 1
        if not best:
            raise TargetPlacementError("target surface has no usable triangle")
        return tuple(best)

    def nearest_vertex_distance(self, point):
        center_cell = self._cell_coord(point)
        seen_cells = set()
        best = float("inf")
        radius = 0
        while radius <= 128:
            low = tuple(center_cell[i] - radius for i in range(3))
            high = tuple(center_cell[i] + radius for i in range(3))
            for ix in range(low[0], high[0] + 1):
                for iy in range(low[1], high[1] + 1):
                    for iz in range(low[2], high[2] + 1):
                        cell = (ix, iy, iz)
                        if cell in seen_cells:
                            continue
                        seen_cells.add(cell)
                        for vertex_index in self._vertex_cells.get(cell, ()):
                            vertex = self.surface.vertices[vertex_index]
                            distance = _norm(_sub(point, vertex))
                            best = min(best, distance)
            if best < float("inf"):
                cube_low = tuple(self.origin[i] + float(center_cell[i] - radius) * self.cell_size for i in range(3))
                cube_high = tuple(cube_low[i] + float(2 * radius + 1) * self.cell_size for i in range(3))
                lower_bound = min(
                    min(float(point[i]) - cube_low[i] for i in range(3)),
                    min(cube_high[i] - float(point[i]) for i in range(3)),
                )
                if best <= lower_bound + 1e-9:
                    break
            radius += 1
        if best == float("inf"):
            raise TargetPlacementError("target surface has no vertices")
        return best


def _closest_point_on_triangle(p, a, b, c):
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = _sub(p, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        return _add(a, _scale(ab, d1 / max(1e-18, d1 - d3)))
    cp = _sub(p, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        return _add(a, _scale(ac, d2 / max(1e-18, d2 - d6)))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        edge = _sub(c, b)
        t = (d4 - d3) / max(1e-18, (d4 - d3) + (d5 - d6))
        return _add(b, _scale(edge, t))
    denom = 1.0 / max(1e-18, va + vb + vc)
    return _add(a, _add(_scale(ab, vb * denom), _scale(ac, vc * denom)))


def _candidate_hits(surface, point, expected_normal=None):
    return list(SurfaceSpatialIndex(surface).nearest_triangles(point, expected_normal, limit=len(surface.triangles)))


def target_surface_anchor(surface, point, expected_normal, ambiguity_tolerance=1e-6, index=None):
    index = index or SurfaceSpatialIndex(surface)
    hits = list(index.nearest_triangles(point, expected_normal, limit=2))
    if not hits:
        raise TargetPlacementError("no unambiguous target surface location matches the garment wrap direction")
    best = hits[0]
    if len(hits) > 1 and abs(hits[1].distance - best.distance) <= float(ambiguity_tolerance) and _dot(best.normal, hits[1].normal) < 0.20:
        raise TargetPlacementError("target surface location is ambiguous for the garment anchor")
    return best


def solve_rigid_z(source_points, target_points, max_translation=600.0, max_rotation=45.0):
    source = tuple(tuple(float(v) for v in p) for p in source_points)
    target = tuple(tuple(float(v) for v in p) for p in target_points)
    if not source or len(source) != len(target):
        raise TargetPlacementError("rigid placement requires equally sized non-empty anchor sets")
    sx = sum(p[0] for p in source) / len(source)
    sy = sum(p[1] for p in source) / len(source)
    tx = sum(p[0] for p in target) / len(target)
    ty = sum(p[1] for p in target) / len(target)
    angle = 0.0
    if len(source) > 1:
        cosine = sine = 0.0
        for a, b in zip(source, target):
            ax, ay = a[0] - sx, a[1] - sy
            bx, by = b[0] - tx, b[1] - ty
            cosine += ax * bx + ay * by
            sine += ax * by - ay * bx
        if abs(cosine) <= 1e-12 and abs(sine) <= 1e-12:
            raise TargetPlacementError("garment anchors do not define a stable rigid orientation")
        angle = atan2(sine, cosine)
    c, s = cos(angle), sin(angle)
    rotated = tuple((c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]) for p in source)
    translation = (
        sum(t[0] - r[0] for t, r in zip(target, rotated)) / len(target),
        sum(t[1] - r[1] for t, r in zip(target, rotated)) / len(target),
        sum(t[2] - r[2] for t, r in zip(target, rotated)) / len(target),
    )
    if _norm(translation) > float(max_translation):
        raise TargetPlacementError("target-aware translation exceeds the configured bound")
    if abs(degrees(angle)) > float(max_rotation):
        raise TargetPlacementError("target-aware rotation exceeds the configured bound")
    transformed = tuple(_add(r, translation) for r in rotated)
    residual = max(_norm(_sub(a, b)) for a, b in zip(transformed, target))
    return RigidDelta(translation, degrees(angle), residual)


def apply_rigid_delta(points, delta):
    c, s = cos(radians(float(delta.rotation_z))), sin(radians(float(delta.rotation_z)))
    t = delta.translation
    return tuple(
        (c * p[0] - s * p[1] + t[0], s * p[0] + c * p[1] + t[1], p[2] + t[2])
        for p in points
    )


def minimum_target_vertex_clearance(surface, points, index=None):
    index = index or SurfaceSpatialIndex(surface)
    if not points:
        raise TargetPlacementError("vertex clearance cannot be measured without garment points")
    minimum = min(index.nearest_vertex_distance(point) for point in points)
    return float(minimum)


def minimum_surface_clearance_detail(surface, points, index=None):
    index = index or SurfaceSpatialIndex(surface)
    minimum = None
    minimum_hit = None
    for point in points:
        hits = index.nearest_triangles(point, limit=1)
        best = hits[0]
        signed = _dot(_sub(point, best.point), best.normal)
        if minimum is None or signed < minimum:
            minimum = signed
            minimum_hit = best
    if minimum is None or minimum_hit is None:
        raise TargetPlacementError("clearance cannot be measured without garment points")
    return float(minimum), minimum_hit


def minimum_surface_clearance(surface, points, index=None):
    actual, _hit = minimum_surface_clearance_detail(surface, points, index=index)
    return actual


def assert_minimum_surface_clearance(surface, points, required_clearance, index=None):
    actual = minimum_surface_clearance(surface, points, index=index)
    required = float(required_clearance)
    if actual < required - 1e-6:
        raise TargetPlacementError(
            "target-aware step-0 clearance %.6f mm is below the required %.6f mm" % (actual, required)
        )
    return actual


def require_ready_target_status(status):
    if not isinstance(status, dict) or status.get("state") != "ready":
        message = status.get("message") if isinstance(status, dict) else None
        raise TargetPlacementError(message or "drape target is not ready")

"""Deterministic surface-aware garment placement primitives.

The placement solver is FreeCAD-independent. Callers provide garment anchor
points in world space, stable avatar target hints, and a wrap direction. The
solver returns a bounded rigid translation and never creates solver pins.
"""
from dataclasses import dataclass
from math import floor, sqrt
from typing import Iterable, Tuple

from freecad_cloth.avatar.AvatarCollision import CollisionSurface

_DIRECTION = {
    "front": (0.0, 1.0, 0.0),
    "back": (0.0, -1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}


@dataclass(frozen=True)
class AnchorQuery:
    name: str
    current_point: Tuple[float, float, float]
    target_hint: Tuple[float, float, float]
    wrap_direction: str

    def validate(self):
        if not str(self.name).strip():
            raise ValueError("placement anchor name must not be empty")
        if self.wrap_direction not in _DIRECTION:
            raise ValueError("placement anchor wrap direction is unsupported")
        if len(self.current_point) != 3 or len(self.target_hint) != 3:
            raise ValueError("placement anchors require three-dimensional points")


@dataclass(frozen=True)
class ClearanceReport:
    minimum: float
    point_index: int
    triangle_index: int


@dataclass(frozen=True)
class PlacementResult:
    translation: Tuple[float, float, float]
    minimum_anchor_clearance: float
    targets: Tuple[Tuple[str, Tuple[float, float, float], Tuple[float, float, float]], ...]


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale(a, value):
    return tuple(float(c) * float(value) for c in a)


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(vector):
    length = sqrt(sum(float(c) * float(c) for c in vector))
    if length <= 1e-12:
        return None
    return tuple(float(c) / length for c in vector)


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
        value = d1 / (d1 - d3)
        return _add(a, _scale(ab, value))
    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        value = d2 / (d2 - d6)
        return _add(a, _scale(ac, value))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        value = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return _add(b, _scale(_sub(c, b), value))
    denominator = 1.0 / (va + vb + vc)
    v = vb * denominator
    w = vc * denominator
    return _add(a, _add(_scale(ab, v), _scale(ac, w)))


def _prepared_surface(surface):
    surface.validate()
    cell_size = max(50.0, min(120.0, 4.0 * max(float(surface.thickness), 1.0)))
    center = surface.center
    prepared = []
    grid = {}

    def cell_coord(point):
        return tuple(int(floor(float(point[i]) / cell_size)) for i in range(3))

    for triangle_index, (ia, ib, ic) in enumerate(surface.triangles):
        a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
        normal = _normalize(_cross(_sub(b, a), _sub(c, a)))
        if normal is None:
            continue
        face_center = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
        if _dot(normal, _sub(center, face_center)) > 0.0:
            normal = _scale(normal, -1.0)
        prepared.append((a, b, c, normal, triangle_index))
        minimum = tuple(min(a[i], b[i], c[i]) - float(surface.thickness) for i in range(3))
        maximum = tuple(max(a[i], b[i], c[i]) + float(surface.thickness) for i in range(3))
        lo = cell_coord(minimum)
        hi = cell_coord(maximum)
        prepared_index = len(prepared) - 1
        for ix in range(lo[0], hi[0] + 1):
            for iy in range(lo[1], hi[1] + 1):
                for iz in range(lo[2], hi[2] + 1):
                    grid.setdefault((ix, iy, iz), []).append(prepared_index)
    return cell_size, prepared, grid


def _candidate_indices(point, cell_size, prepared, grid):
    cell = tuple(int(floor(float(point[i]) / cell_size)) for i in range(3))
    for radius in (0, 1, 2, 3):
        candidates = set()
        for ix in range(cell[0] - radius, cell[0] + radius + 1):
            for iy in range(cell[1] - radius, cell[1] + radius + 1):
                for iz in range(cell[2] - radius, cell[2] + radius + 1):
                    candidates.update(grid.get((ix, iy, iz), ()))
        if candidates:
            return tuple(sorted(candidates))
    return tuple(range(len(prepared)))


def nearest_surface_anchor(surface: CollisionSurface, target_hint, wrap_direction: str):
    """Return the deterministic surface point and outward normal near a landmark."""
    if wrap_direction not in _DIRECTION:
        raise ValueError("placement anchor wrap direction is unsupported")
    cell_size, prepared, grid = _prepared_surface(surface)
    if not prepared:
        raise ValueError("target surface contains no usable triangles")
    point = tuple(float(v) for v in target_hint)
    preferred = _DIRECTION[wrap_direction]
    candidates = _candidate_indices(point, cell_size, prepared, grid)
    ranked = []
    for prepared_index in candidates:
        a, b, c, normal, triangle_index = prepared[prepared_index]
        closest = _closest_point_triangle(point, a, b, c)
        distance_sq = _dot(_sub(closest, point), _sub(closest, point))
        facing_penalty = 0 if _dot(normal, preferred) >= 0.05 else 1
        ranked.append((facing_penalty, distance_sq, -_dot(normal, preferred), triangle_index, closest, normal))
    facing = [value for value in ranked if value[0] == 0]
    chosen = min(facing or ranked, key=lambda value: value[:4])
    return chosen[4], chosen[5], chosen[3]


def surface_clearance(points: Iterable[Tuple[float, float, float]], surface: CollisionSurface) -> ClearanceReport:
    """Return the minimum signed outward clearance for the supplied points."""
    cell_size, prepared, grid = _prepared_surface(surface)
    points = tuple(tuple(float(v) for v in point) for point in points)
    if not points:
        raise ValueError("at least one point is required for clearance validation")
    minimum = None
    minimum_index = -1
    minimum_triangle = -1
    for point_index, point in enumerate(points):
        best = None
        for prepared_index in _candidate_indices(point, cell_size, prepared, grid):
            a, b, c, normal, triangle_index = prepared[prepared_index]
            closest = _closest_point_triangle(point, a, b, c)
            delta = _sub(point, closest)
            candidate = (_dot(delta, delta), _dot(delta, normal), triangle_index)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            continue
        _, signed, triangle_index = best
        if minimum is None or signed < minimum:
            minimum = signed
            minimum_index = point_index
            minimum_triangle = triangle_index
    if minimum is None:
        raise ValueError("target surface contains no usable triangles")
    return ClearanceReport(float(minimum), minimum_index, minimum_triangle)


def solve_anchor_translation(
    surface: CollisionSurface,
    anchors: Iterable[AnchorQuery],
    clearance: float = 6.0,
    max_translation: float = 200.0,
    tolerance: float = 1e-6,
) -> PlacementResult:
    """Solve a bounded rigid translation from garment anchors to target hints."""
    if float(clearance) < 0.0:
        raise ValueError("placement clearance must be non-negative")
    if float(max_translation) <= 0.0:
        raise ValueError("placement maximum translation must be positive")
    queries = tuple(anchors)
    if not queries:
        raise ValueError("at least one garment placement anchor is required")
    for query in queries:
        query.validate()
    targets = []
    deltas = []
    for query in queries:
        target_point, normal, _triangle_index = nearest_surface_anchor(
            surface, query.target_hint, query.wrap_direction
        )
        desired = _add(target_point, _scale(normal, float(clearance)))
        deltas.append(_sub(desired, query.current_point))
        targets.append((str(query.name), tuple(desired), tuple(normal)))
    translation = tuple(sum(delta[i] for delta in deltas) / len(deltas) for i in range(3))
    length = sqrt(_dot(translation, translation))
    if length > float(max_translation) + float(tolerance):
        raise ValueError(
            "target-aware placement requires %.3f mm translation; maximum is %.3f mm"
            % (length, float(max_translation))
        )
    moved = tuple(_add(query.current_point, translation) for query in queries)
    report = surface_clearance(moved, surface)
    if report.minimum + float(tolerance) < float(clearance):
        raise ValueError(
            "target-aware placement could not satisfy %.3f mm anchor clearance; minimum is %.3f mm"
            % (float(clearance), report.minimum)
        )
    return PlacementResult(
        tuple(float(v) for v in translation),
        float(report.minimum),
        tuple(targets),
    )

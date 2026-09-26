"""Deterministic target-aware rigid placement helpers.

The geometry layer is solver-neutral: it consumes a DrapeTarget CollisionSurface
and world-space garment sample points, then returns a bounded rigid translation.
"""
from math import sqrt
from freecad_cloth.avatar.AvatarCollision import CollisionSurface


def _sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _add(a, b):
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _scale(v, factor):
    return (float(v[0]) * factor, float(v[1]) * factor, float(v[2]) * factor)


def _dot(a, b):
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _length(v):
    return sqrt(_dot(v, v))


def _normalize(v, fallback=(0.0, 0.0, 1.0)):
    length = _length(v)
    if length <= 1e-12:
        return tuple(float(x) for x in fallback)
    return _scale(v, 1.0 / length)


def _closest_point_on_triangle(point, a, b, c):
    """Return the closest point on a triangle using the standard Voronoi regions."""
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
        denom = d1 - d3
        t = d1 / denom if abs(denom) > 1e-12 else 0.0
        return _add(a, _scale(ab, t))
    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denom = d2 - d6
        t = d2 / denom if abs(denom) > 1e-12 else 0.0
        return _add(a, _scale(ac, t))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        edge = _sub(c, b)
        denom = (d4 - d3) + (d5 - d6)
        t = (d4 - d3) / denom if abs(denom) > 1e-12 else 0.0
        return _add(b, _scale(edge, t))
    denom = va + vb + vc
    if abs(denom) <= 1e-12:
        return min((a, b, c), key=lambda candidate: _length(_sub(point, candidate)))
    v = vb / denom
    w = vc / denom
    return _add(a, _add(_scale(ab, v), _scale(ac, w)))


def nearest_surface_point(point, surface: CollisionSurface):
    surface.validate()
    best_point = None
    best_distance_sq = float("inf")
    best_triangle = None
    for index, triangle in enumerate(surface.triangles):
        a, b, c = (surface.vertices[int(i)] for i in triangle)
        candidate = _closest_point_on_triangle(point, a, b, c)
        delta = _sub(point, candidate)
        distance_sq = _dot(delta, delta)
        if distance_sq < best_distance_sq:
            best_point = candidate
            best_distance_sq = distance_sq
            best_triangle = index
    if best_point is None:
        raise ValueError("drape target surface contains no triangles")
    return best_point, sqrt(max(0.0, best_distance_sq)), best_triangle


def surface_outward_direction(point, surface: CollisionSurface):
    """Estimate an outward direction from target geometry using the target centroid."""
    nearest, _distance, _triangle = nearest_surface_point(point, surface)
    return _normalize(_sub(nearest, surface.center), _normalize(_sub(point, surface.center)))


def minimum_signed_clearance(points, surface: CollisionSurface, outward):
    """Return the minimum radial signed clearance, accounting for target thickness."""
    direction = _normalize(outward)
    minimum = float("inf")
    for point in points:
        nearest, _distance, _triangle = nearest_surface_point(point, surface)
        signed = _dot(_sub(point, nearest), direction) - float(surface.thickness)
        minimum = min(minimum, signed)
    return minimum if minimum != float("inf") else None


def rigid_translation_for_clearance(points, surface: CollisionSurface, clearance=5.0, max_translation=250.0):
    """Solve a deterministic outward-only rigid translation.

    Rotation is intentionally unchanged in this first bounded contract. A rigid
    translation is therefore lossless under HomePlacement/reset and cannot
    introduce garment deformation or solver-specific constraints.
    """
    surface.validate()
    samples = tuple(tuple(float(c) for c in point) for point in points)
    if not samples:
        raise ValueError("garment has no geometry points for target placement")
    clearance = max(0.0, float(clearance))
    max_translation = max(0.0, float(max_translation))
    center = tuple(sum(point[i] for point in samples) / len(samples) for i in range(3))
    direction = _normalize(_sub(center, surface.center))
    total = 0.0
    for _ in range(8):
        signed = minimum_signed_clearance(samples, surface, direction)
        if signed is None:
            raise ValueError("cannot measure target clearance")
        deficit = clearance - float(signed)
        if deficit <= 1e-6:
            return (0.0, 0.0, 0.0) if total <= 1e-12 else _scale(direction, total)
        if total + deficit > max_translation + 1e-9:
            raise ValueError(
                "target-relative placement exceeds translation bound: %.3f > %.3f"
                % (total + deficit, max_translation)
            )
        delta = _scale(direction, deficit)
        samples = tuple(_add(point, delta) for point in samples)
        total += deficit
    signed = minimum_signed_clearance(samples, surface, direction)
    if signed is None or signed < clearance - 1e-4:
        raise ValueError("target-relative placement did not reach required clearance")
    return _scale(direction, total)

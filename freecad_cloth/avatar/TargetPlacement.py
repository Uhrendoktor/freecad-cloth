"""Deterministic solver-neutral target placement geometry helpers.

This module intentionally has no FreeCAD dependency. It operates on the small
CollisionSurface contract already used by the fitting and simulation layers.
"""

from dataclasses import dataclass
from math import sqrt


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


def target_surface_anchor(surface, point, *,
                           ambiguity_tolerance=DEFAULT_AMBIGUITY_TOLERANCE):
    """Return the nearest outward-facing surface point and normal.

    A near-tie with materially different/opposing normals is rejected rather
    than selecting an arbitrary triangle at a fold or self-intersection.
    """
    vertices, triangles, center = _surface_triangle_data(surface)
    point = tuple(float(value) for value in point)
    candidates = []
    for triangle_index, triangle in enumerate(triangles):
        a, b, c = (vertices[triangle[0]], vertices[triangle[1]], vertices[triangle[2]])
        try:
            normal = _outward_normal(a, b, c, center)
        except ValueError:
            continue
        closest = _closest_point_on_triangle(point, a, b, c)
        distance = _norm(_sub(point, closest))
        candidates.append(
            TargetSurfaceHit(triangle_index, closest, normal, distance)
        )
    if not candidates:
        raise ValueError("target collision surface contains no usable triangle normals")
    candidates.sort(key=lambda hit: (hit.distance, hit.triangle_index))
    best = candidates[0]
    for other in candidates[1:]:
        if abs(other.distance - best.distance) > float(ambiguity_tolerance):
            break
        if _norm(_sub(other.point, best.point)) > 1e-5 or _dot(other.normal, best.normal) < 0.20:
            raise ValueError("target snap anchor is ambiguous across surface normals")
    return best


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


def nearest_surface_distance(surface, points):
    """Return the minimum unsigned point-to-surface distance."""
    vertices, triangles, _center = _surface_triangle_data(surface)
    minimum = float("inf")
    for point in points:
        point = tuple(float(value) for value in point)
        for triangle in triangles:
            closest = _closest_point_on_triangle(
                point, vertices[triangle[0]], vertices[triangle[1]], vertices[triangle[2]]
            )
            minimum = min(minimum, _norm(_sub(point, closest)))
    return minimum

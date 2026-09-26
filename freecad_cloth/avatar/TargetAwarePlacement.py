"""Deterministic, solver-neutral rigid garment placement against a target surface."""
from dataclasses import dataclass
from math import atan2, cos, degrees, radians, sin, sqrt


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


def _triangle_data(surface, index):
    try:
        ia, ib, ic = surface.triangles[index]
        a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
    except (IndexError, TypeError, ValueError) as exc:
        raise TargetPlacementError("target surface triangle data is invalid") from exc
    normal = _unit(_cross(_sub(b, a), _sub(c, a)))
    center = _scale(_add(_add(a, b), c), 1.0 / 3.0)
    if _dot(normal, _sub(center, _surface_center(surface))) < 0.0:
        normal = _scale(normal, -1.0)
    return tuple(a), tuple(b), tuple(c), normal


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
    expected = _unit(expected_normal) if expected_normal is not None else None
    hits = []
    for index in range(len(surface.triangles)):
        a, b, c, normal = _triangle_data(surface, index)
        if expected is not None and _dot(normal, expected) < 0.20:
            continue
        closest = _closest_point_on_triangle(point, a, b, c)
        hits.append(SurfaceHit(index, closest, normal, _norm(_sub(point, closest))))
    return hits


def target_surface_anchor(surface, point, expected_normal, ambiguity_tolerance=1e-6):
    hits = sorted(_candidate_hits(surface, point, expected_normal), key=lambda h: (round(h.distance, 12), h.triangle_index))
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


def minimum_surface_clearance(surface, points):
    minimum = None
    for point in points:
        hits = sorted(_candidate_hits(surface, point), key=lambda h: (round(h.distance, 12), h.triangle_index))
        if not hits:
            raise TargetPlacementError("target surface has no usable triangle")
        best = hits[0]
        signed = _dot(_sub(point, best.point), best.normal)
        minimum = signed if minimum is None else min(minimum, signed)
    if minimum is None:
        raise TargetPlacementError("clearance cannot be measured without garment points")
    return float(minimum)


def assert_minimum_surface_clearance(surface, points, required_clearance):
    actual = minimum_surface_clearance(surface, points)
    required = float(required_clearance)
    if actual < required - 1e-6:
        raise TargetPlacementError(
            "target-aware step-0 clearance %.6f mm is below the required %.6f mm" % (actual, required)
        )
    return actual


def transform_surface(surface, transform_point):
    """Return a CollisionSurface transformed into the caller's world coordinate frame."""
    transformed = tuple(
        tuple(float(value) for value in transform_point(tuple(float(v) for v in point)))
        for point in surface.vertices
    )
    result = surface.__class__(transformed, surface.triangles, surface.region, surface.thickness)
    result.validate()
    return result


def require_ready_target_status(status):
    if not isinstance(status, dict) or status.get("state") != "ready":
        message = status.get("message") if isinstance(status, dict) else None
        raise TargetPlacementError(message or "drape target is not ready")

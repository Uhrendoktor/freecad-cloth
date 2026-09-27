"""Deterministic, solver-neutral rigid garment placement against a persistent target surface."""
from dataclasses import dataclass
from math import atan2, cos, degrees, isfinite, sqrt, sin, radians


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


def _scale(a, value):
    return tuple(float(a[i]) * float(value) for i in range(3))


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(value):
    return sqrt(max(0.0, _dot(value, value)))


def _unit(value):
    length = _norm(value)
    if length <= 1e-12:
        raise TargetPlacementError("target surface contains a degenerate triangle")
    return _scale(value, 1.0 / length)


def wrap_normal(direction):
    try:
        return _WRAP_NORMALS[str(direction)]
    except KeyError as exc:
        raise TargetPlacementError("unsupported garment wrap direction: %s" % direction) from exc


def _closest_point_on_triangle(point, a, b, c):
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(point, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = _sub(point, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        return _add(a, _scale(ab, d1 / max(1e-18, d1 - d3)))
    cp = _sub(point, c)
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


def _triangle_normal(surface, triangle_index):
    ia, ib, ic = surface.triangles[triangle_index]
    a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
    normal = _unit(_cross(_sub(b, a), _sub(c, a)))
    center = surface.center
    triangle_center = _scale(_add(_add(a, b), c), 1.0 / 3.0)
    if _dot(normal, _sub(triangle_center, center)) < 0.0:
        normal = _scale(normal, -1.0)
    return tuple(float(v) for v in normal)


def target_surface_anchor(surface, point, expected_normal, *, index=None):
    """Return the nearest deterministic triangle whose outward normal matches the wrap side."""
    expected = _unit(expected_normal)
    candidates = []
    indices = range(len(surface.triangles)) if index is None else index
    for triangle_index in indices:
        normal = _triangle_normal(surface, triangle_index)
        alignment = _dot(normal, expected)
        if alignment < 0.20:
            continue
        ia, ib, ic = surface.triangles[triangle_index]
        closest = _closest_point_on_triangle(
            point, surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
        )
        distance = _norm(_sub(point, closest))
        candidates.append(
            SurfaceHit(triangle_index, closest, normal, distance)
        )
    if not candidates:
        raise TargetPlacementError("no target surface triangle matches the garment wrap direction")
    candidates.sort(key=lambda hit: (round(hit.distance, 12), hit.triangle_index))
    if len(candidates) > 1 and abs(candidates[1].distance - candidates[0].distance) <= 1e-9:
        if _dot(candidates[0].normal, candidates[1].normal) < 0.20:
            raise TargetPlacementError("target surface anchor is ambiguous")
    return candidates[0]


def solve_rigid_z(source_points, target_points, *, max_translation=600.0, max_rotation=45.0):
    """Solve one shared planar rigid transform; pairwise source spacing is preserved."""
    source = tuple(tuple(float(v) for v in p) for p in source_points)
    target = tuple(tuple(float(v) for v in p) for p in target_points)
    if not source or len(source) != len(target):
        raise TargetPlacementError("rigid placement requires equally sized non-empty anchors")
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



def nearest_target_projection(surface, point):
    """Return the nearest deterministic outward projection without imposing a guessed wrap axis."""
    candidates = []
    for triangle_index in range(len(surface.triangles)):
        normal = _triangle_normal(surface, triangle_index)
        ia, ib, ic = surface.triangles[triangle_index]
        closest = _closest_point_on_triangle(
            point, surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
        )
        distance = _norm(_sub(point, closest))
        candidates.append(SurfaceHit(triangle_index, closest, normal, distance))
    if not candidates:
        raise TargetPlacementError("target surface has no triangles")
    candidates.sort(key=lambda hit: (round(hit.distance, 12), hit.triangle_index))
    best = candidates[0]
    for candidate in candidates[1:]:
        if abs(candidate.distance - best.distance) > 1e-9:
            break
        if _dot(best.normal, candidate.normal) < 0.20:
            raise TargetPlacementError("target projection is ambiguous across opposing surface normals")
    return best


def solve_shared_translation(source_points, target_points, *, max_translation=600.0):
    """Solve one bounded rigid translation; pairwise garment spacing and rotations are unchanged."""
    source = tuple(tuple(float(v) for v in p) for p in source_points)
    target = tuple(tuple(float(v) for v in p) for p in target_points)
    if not source or len(source) != len(target):
        raise TargetPlacementError("shared translation requires equally sized non-empty anchors")
    translation = tuple(
        sum(target[i][axis] - source[i][axis] for i in range(len(source))) / len(source)
        for axis in range(3)
    )
    if _norm(translation) > float(max_translation):
        raise TargetPlacementError("target-aware translation exceeds the configured bound")
    residual = max(
        _norm(_sub(_add(source_point, translation), target_point))
        for source_point, target_point in zip(source, target)
    )
    return RigidDelta(translation, 0.0, residual)


def minimum_surface_clearance(surface, points):
    """Return the minimum signed clearance of world-space garment samples from the target."""
    if not points:
        raise TargetPlacementError("at least one garment sample point is required")
    best = None
    for index, point in enumerate(points):
        hit = nearest_target_projection(surface, point)
        signed = _dot(_sub(point, hit.point), hit.normal)
        if not isfinite(signed):
            raise TargetPlacementError("target clearance became non-finite")
        record = (float(signed), index, hit)
        if best is None or record[0] < best[0]:
            best = record
    return float(best[0])

def apply_rigid_delta(points, delta):
    angle = radians(float(delta.rotation_z))
    c, s = cos(angle), sin(angle)
    tx, ty, tz = delta.translation
    return tuple(
        (
            c * p[0] - s * p[1] + tx,
            s * p[0] + c * p[1] + ty,
            p[2] + tz,
        )
        for p in points
    )


def anchor_clearance(surface, point, expected_normal, *, index=None):
    hit = target_surface_anchor(surface, point, expected_normal, index=index)
    return _dot(_sub(point, hit.point), hit.normal)


def minimum_anchor_clearance(surface, anchors, *, index=None):
    if not anchors:
        raise TargetPlacementError("at least one target-aware anchor is required")
    values = [
        anchor_clearance(surface, point, normal, index=index)
        for point, normal in anchors
    ]
    return float(min(values))

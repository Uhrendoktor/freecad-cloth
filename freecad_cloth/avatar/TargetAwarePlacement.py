"""Deterministic, solver-neutral rigid placement against a persistent collision surface."""
from dataclasses import dataclass
from math import atan2, cos, degrees, isfinite, radians, sin, sqrt

MAX_ANCHORS_PER_PIECE = 8
DEFAULT_AMBIGUITY_TOLERANCE = 1e-6
DEFAULT_POINT_TOLERANCE = 1e-5


class TargetPlacementError(ValueError):
    """Raised whenever a bounded target-aware placement cannot be proven safe."""


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
    # Canonical FreeCAD human mannequin: front is -Y and back is +Y.
    "front": (0.0, 1.0, 0.0),
    "back": (0.0, -1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}


def _require_finite(values, label):
    for value in values:
        if not isfinite(float(value)):
            raise TargetPlacementError("%s contains a non-finite value" % label)


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale(a, factor):
    return tuple(float(a[i]) * float(factor) for i in range(3))


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


def _unit(a, label):
    _require_finite(a, label)
    length = _norm(a)
    if length <= 1e-12:
        raise TargetPlacementError("%s must be non-zero" % label)
    return _scale(a, 1.0 / length)


def wrap_normal(wrap_direction):
    try:
        return _WRAP_NORMALS[str(wrap_direction)]
    except KeyError as exc:
        raise TargetPlacementError("unsupported garment wrap direction") from exc


def _validated_surface(surface):
    try:
        surface.validate()
        vertices = tuple(tuple(float(c) for c in vertex) for vertex in surface.vertices)
        triangles = tuple(tuple(int(i) for i in tri) for tri in surface.triangles)
    except (AttributeError, TypeError, ValueError) as exc:
        raise TargetPlacementError("target surface is invalid") from exc
    for vertex in vertices:
        _require_finite(vertex, "target surface vertex")
    if len(vertices) < 3 or not triangles:
        raise TargetPlacementError("target surface has no usable triangles")
    for tri in triangles:
        if len(tri) != 3 or any(index < 0 or index >= len(vertices) for index in tri):
            raise TargetPlacementError("target surface triangle index is invalid")
    return vertices, triangles


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
    denominator = max(1e-18, va + vb + vc)
    return _add(a, _add(_scale(ab, vb / denominator), _scale(ac, vc / denominator)))


def _surface_normal(surface, a, b, c):
    normal = _unit(_cross(_sub(b, a), _sub(c, a)), "target surface normal")
    triangle_center = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
    center = tuple(float(v) for v in surface.center)
    if _dot(normal, _sub(triangle_center, center)) < 0.0:
        normal = _scale(normal, -1.0)
    return normal


def _candidate_hits(surface, point, expected_normal):
    vertices, triangles = _validated_surface(surface)
    point = tuple(float(v) for v in point)
    _require_finite(point, "garment anchor")
    expected = _unit(expected_normal, "expected wrap normal")
    hits = []
    for index, tri in enumerate(triangles):
        a, b, c = (vertices[tri[0]], vertices[tri[1]], vertices[tri[2]])
        normal = _surface_normal(surface, a, b, c)
        if _dot(normal, expected) < 0.20:
            continue
        closest = _closest_point_on_triangle(point, a, b, c)
        hits.append(SurfaceHit(index, closest, normal, _norm(_sub(point, closest))))
    return hits


def target_surface_anchor(surface, point, expected_normal,
                           ambiguity_tolerance=DEFAULT_AMBIGUITY_TOLERANCE,
                           point_tolerance=DEFAULT_POINT_TOLERANCE):
    hits = sorted(
        _candidate_hits(surface, point, expected_normal),
        key=lambda hit: (round(float(hit.distance), 12), int(hit.triangle_index)),
    )
    if not hits:
        raise TargetPlacementError("no unambiguous target surface location matches the garment wrap direction")
    best = hits[0]
    for other in hits[1:]:
        if abs(float(other.distance) - float(best.distance)) > float(ambiguity_tolerance):
            break
        if _norm(_sub(other.point, best.point)) > float(point_tolerance) or _dot(best.normal, other.normal) < 0.20:
            raise TargetPlacementError("target surface location is ambiguous for the garment anchor")
    return best


def solve_rigid_z(source_points, target_points, max_translation=600.0, max_rotation=45.0):
    source = tuple(tuple(float(v) for v in point) for point in source_points)
    target = tuple(tuple(float(v) for v in point) for point in target_points)
    if not source or len(source) != len(target):
        raise TargetPlacementError("rigid placement requires equally sized non-empty anchor sets")
    if len(source) > MAX_ANCHORS_PER_PIECE:
        raise TargetPlacementError("rigid placement exceeds the anchor-count bound")
    for point in source:
        _require_finite(point, "source anchor")
    for point in target:
        _require_finite(point, "target anchor")
    if float(max_translation) < 0.0 or float(max_rotation) < 0.0:
        raise TargetPlacementError("placement bounds must be non-negative")
    sx = sum(point[0] for point in source) / len(source)
    sy = sum(point[1] for point in source) / len(source)
    tx = sum(point[0] for point in target) / len(target)
    ty = sum(point[1] for point in target) / len(target)
    angle = 0.0
    if len(source) > 1:
        cosine = sine = 0.0
        for source_point, target_point in zip(source, target):
            ax, ay = source_point[0] - sx, source_point[1] - sy
            bx, by = target_point[0] - tx, target_point[1] - ty
            cosine += ax * bx + ay * by
            sine += ax * by - ay * bx
        if abs(cosine) <= 1e-12 and abs(sine) <= 1e-12:
            raise TargetPlacementError("garment anchors do not define a stable rigid orientation")
        angle = atan2(sine, cosine)
    c, s = cos(angle), sin(angle)
    rotated = tuple(
        (c * point[0] - s * point[1], s * point[0] + c * point[1], point[2])
        for point in source
    )
    translation = (
        sum(target_point[0] - rotated_point[0] for target_point, rotated_point in zip(target, rotated)) / len(target),
        sum(target_point[1] - rotated_point[1] for target_point, rotated_point in zip(target, rotated)) / len(target),
        sum(target_point[2] - rotated_point[2] for target_point, rotated_point in zip(target, rotated)) / len(target),
    )
    if _norm(translation) > float(max_translation) + 1e-9:
        raise TargetPlacementError("target-aware translation exceeds the configured bound")
    if abs(degrees(angle)) > float(max_rotation) + 1e-9:
        raise TargetPlacementError("target-aware rotation exceeds the configured bound")
    transformed = tuple(_add(rotated_point, translation) for rotated_point in rotated)
    residual = max(_norm(_sub(left, right)) for left, right in zip(transformed, target))
    return RigidDelta(tuple(translation), degrees(angle), residual)


def apply_rigid_delta(points, delta):
    c, s = cos(radians(float(delta.rotation_z))), sin(radians(float(delta.rotation_z)))
    translation = tuple(float(value) for value in delta.translation)
    return tuple(
        (c * point[0] - s * point[1] + translation[0],
         s * point[0] + c * point[1] + translation[1],
         point[2] + translation[2])
        for point in points
    )


def minimum_surface_clearance(surface, points):
    vertices, triangles = _validated_surface(surface)
    positions = tuple(tuple(float(v) for v in point) for point in points)
    if not positions:
        raise TargetPlacementError("clearance requires at least one garment point")
    minimum = None
    for point in positions:
        _require_finite(point, "garment point")
        nearest = None
        for index, tri in enumerate(triangles):
            a, b, c = (vertices[tri[0]], vertices[tri[1]], vertices[tri[2]])
            normal = _surface_normal(surface, a, b, c)
            closest = _closest_point_on_triangle(point, a, b, c)
            signed = _dot(_sub(point, closest), normal)
            candidate = (abs(signed), index, signed)
            if nearest is None or (round(candidate[0], 12), candidate[1]) < (round(nearest[0], 12), nearest[1]):
                nearest = candidate
        if nearest is None:
            raise TargetPlacementError("target surface has no usable triangle")
        minimum = float(nearest[2]) if minimum is None else min(minimum, float(nearest[2]))
    return float(minimum)


def clearance_correction_vector(surface, points, required_clearance):
    """Return one deterministic bounded translation that raises the worst clearance."""
    required = float(required_clearance)
    if required < 0.0:
        raise TargetPlacementError("required clearance must be non-negative")
    vertices, triangles = _validated_surface(surface)
    positions = tuple(tuple(float(v) for v in point) for point in points)
    if not positions:
        raise TargetPlacementError("clearance correction requires at least one garment point")
    candidates = []
    for point_index, point in enumerate(positions):
        _require_finite(point, "garment point")
        for triangle_index, tri in enumerate(triangles):
            a, b, c = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]
            normal = _unit(_cross(_sub(b, a), _sub(c, a)), "target surface normal")
            closest = _closest_point_on_triangle(point, a, b, c)
            signed = _dot(_sub(point, closest), normal)
            gap = required - float(signed)
            if gap > 1e-9:
                candidates.append((float(gap), int(point_index), int(triangle_index), normal))
    if not candidates:
        return (0.0, 0.0, 0.0)
    gap, _point_index, _triangle_index, normal = max(
        candidates, key=lambda item: (round(item[0], 12), -item[1], -item[2])
    )
    return _scale(normal, gap)


def assert_minimum_surface_clearance(surface, points, required_clearance):
    required = float(required_clearance)
    if required < 0.0:
        raise TargetPlacementError("required clearance must be non-negative")
    actual = minimum_surface_clearance(surface, points)
    if actual < required - 1e-6:
        raise TargetPlacementError(
            "target-aware step-0 clearance %.6f mm is below the required %.6f mm" % (actual, required)
        )
    return actual


def require_ready_target_status(status):
    if not isinstance(status, dict) or str(status.get("state", "")) != "ready":
        message = status.get("message") if isinstance(status, dict) else None
        raise TargetPlacementError(message or "drape target is not ready")

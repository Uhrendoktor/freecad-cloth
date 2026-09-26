"""Deterministic, solver-neutral placement math against an authoritative collision surface.

The module deliberately knows nothing about FreeCAD. Runtime adapters provide world-space
points and a validated CollisionSurface, then use these helpers to place garment anchors
outside the target before simulation.
"""
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
    """Return the Euclidean closest point on triangle ABC."""
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
        edge = _vsub(c, b)
        scale = (d4 - d3) / max(1e-12, (d4 - d3) + (d5 - d6))
        return _vadd(b, _vmul(edge, scale))

    denominator = 1.0 / max(1e-12, va + vb + vc)
    v = vb * denominator
    w = vc * denominator
    return _vadd(a, _vadd(_vmul(ab, v), _vmul(ac, w)))


def _oriented_outward_normal(a: Vector, b: Vector, c: Vector, center: Vector) -> Vector:
    normal = _normalize(_cross(_vsub(b, a), _vsub(c, a)))
    triangle_center = _vmul(_vadd(_vadd(a, b), c), 1.0 / 3.0)
    if _dot(normal, _vsub(triangle_center, center)) < 0.0:
        normal = _vmul(normal, -1.0)
    return normal


@dataclass(frozen=True)
class TargetProjection:
    triangle_index: int
    point: Vector
    normal: Vector
    distance: float


def nearest_target_projection(point: Vector, surface, expected_normal: Vector = None, ambiguity_tolerance: float = 1e-6) -> TargetProjection:
    """Find the nearest target triangle and orient its normal away from surface.center.

    A near-equal nearest projection with a materially different normal is rejected
    as ambiguous rather than making a hidden side/orientation choice.
    """
    surface.validate()
    query = tuple(float(value) for value in point)
    expected = _normalize(expected_normal) if expected_normal is not None else None
    best = None
    candidates = []
    for index, triangle in enumerate(surface.triangles):
        a, b, c = (surface.vertices[int(i)] for i in triangle)
        try:
            normal = _oriented_outward_normal(a, b, c, surface.center)
        except ValueError:
            continue
        if expected is not None and _dot(normal, expected) < 0.20:
            continue
        closest = _closest_point_on_triangle(query, a, b, c)
        distance = _norm(_vsub(query, closest))
        if best is None or distance < best.distance:
            best = TargetProjection(index, closest, normal, distance)
            candidates = [best]
        elif abs(distance - best.distance) <= max(float(ambiguity_tolerance), best.distance * 1e-9):
            candidates.append(TargetProjection(index, closest, normal, distance))
    if best is None:
        raise ValueError("target surface has no usable non-degenerate triangles")
    for candidate in candidates:
        if candidate.triangle_index == best.triangle_index:
            continue
        if _dot(candidate.normal, best.normal) < 0.5:
            raise ValueError("target projection is ambiguous across opposing surface normals")
    return best



@dataclass(frozen=True)
class RigidDelta:
    translation: Vector
    rotation_z: float
    residual_max: float


def wrap_normal(wrap_direction: str) -> Vector:
    normals = {
        "front": (0.0, -1.0, 0.0),
        "back": (0.0, 1.0, 0.0),
        "left": (-1.0, 0.0, 0.0),
        "right": (1.0, 0.0, 0.0),
    }
    try:
        return normals[str(wrap_direction)]
    except KeyError as exc:
        raise ValueError("unsupported garment wrap direction") from exc


def solve_rigid_z(source_points: Iterable[Vector], target_points: Iterable[Vector], max_translation: float = 750.0, max_rotation: float = 45.0) -> RigidDelta:
    """Return a deterministic rigid world-Z rotation plus translation for anchor pairs."""
    from math import atan2, cos, degrees, sin
    source = tuple(tuple(float(v) for v in point) for point in source_points)
    target = tuple(tuple(float(v) for v in point) for point in target_points)
    if not source or len(source) != len(target):
        raise ValueError("rigid target placement requires equally sized non-empty anchor sets")
    sx = sum(point[0] for point in source) / len(source)
    sy = sum(point[1] for point in source) / len(source)
    tx = sum(point[0] for point in target) / len(target)
    ty = sum(point[1] for point in target) / len(target)
    angle = 0.0
    if len(source) > 1:
        cosine = sine = 0.0
        for a, b in zip(source, target):
            ax, ay = a[0] - sx, a[1] - sy
            bx, by = b[0] - tx, b[1] - ty
            cosine += ax * bx + ay * by
            sine += ax * by - ay * bx
        if abs(cosine) <= 1e-12 and abs(sine) <= 1e-12:
            raise ValueError("garment anchors do not define a stable rigid orientation")
        angle = atan2(sine, cosine)
    c, s = cos(angle), sin(angle)
    rotated = tuple((c * point[0] - s * point[1], s * point[0] + c * point[1], point[2]) for point in source)
    translation = tuple(
        sum(target_point[i] - rotated_point[i] for target_point, rotated_point in zip(target, rotated)) / len(target)
        for i in range(3)
    )
    travel = _norm(translation)
    rotation = abs(degrees(angle))
    if travel > float(max_translation) + 1e-9:
        raise ValueError("target-aware placement exceeds the translation guard: %.6f > %.6f" % (travel, float(max_translation)))
    if rotation > float(max_rotation) + 1e-9:
        raise ValueError("target-aware placement exceeds the rotation guard: %.6f > %.6f" % (rotation, float(max_rotation)))
    transformed = tuple(_vadd(rotated_point, translation) for rotated_point in rotated)
    residual = max(_norm(_vsub(a, b)) for a, b in zip(transformed, target))
    return RigidDelta(translation, degrees(angle), residual)


def signed_target_clearance(point: Vector, surface) -> float:
    """Return center-oriented signed clearance to the nearest target surface."""
    projection = nearest_target_projection(point, surface)
    return _dot(_vsub(tuple(float(v) for v in point), projection.point), projection.normal)


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


def required_translation_for_clearance(points: Iterable[Vector], surface, clearance: float, normal: Vector, max_translation: float) -> float:
    """Return a bounded outward correction amount for a translated garment sample set."""
    required = max(0.0, float(clearance) - minimum_signed_clearance(points, surface).minimum_signed_clearance)
    if required > float(max_translation) + 1e-9:
        raise ValueError(
            "target-aware placement exceeds the translation guard: %.6f > %.6f" %
            (required, float(max_translation))
        )
    if _norm(normal) <= 1e-12:
        raise ValueError("target placement correction normal is degenerate")
    return required


def average_point(points: Iterable[Vector]) -> Vector:
    return _average(points)

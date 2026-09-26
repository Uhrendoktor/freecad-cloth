"""Deterministic, solver-neutral placement math against an authoritative collision surface."""
from dataclasses import dataclass
from math import sqrt, isfinite
from typing import Iterable, Tuple

Vector = Tuple[float, float, float]


def _vadd(a, b): return tuple(float(a[i]) + float(b[i]) for i in range(3))
def _vsub(a, b): return tuple(float(a[i]) - float(b[i]) for i in range(3))
def _vmul(a, scalar): return tuple(float(a[i]) * float(scalar) for i in range(3))
def _dot(a, b): return sum(float(a[i]) * float(b[i]) for i in range(3))
def _cross(a, b):
    return (float(a[1])*float(b[2])-float(a[2])*float(b[1]),
            float(a[2])*float(b[0])-float(a[0])*float(b[2]),
            float(a[0])*float(b[1])-float(a[1])*float(b[0]))
def _norm(a): return sqrt(max(0.0, _dot(a,a)))


def _normalize(a):
    length = _norm(a)
    if length <= 1e-12:
        raise ValueError("target triangle normal is degenerate")
    return _vmul(a, 1.0 / length)


def _average(points):
    values = tuple(points)
    if not values:
        raise ValueError("at least one point is required")
    scale = 1.0 / len(values)
    return tuple(sum(float(point[i]) for point in values) * scale for i in range(3))


def _closest_point_on_triangle(point, a, b, c):
    ab, ac, ap = _vsub(b,a), _vsub(c,a), _vsub(point,a)
    d1, d2 = _dot(ab,ap), _dot(ac,ap)
    if d1 <= 0.0 and d2 <= 0.0: return a
    bp = _vsub(point,b); d3, d4 = _dot(ab,bp), _dot(ac,bp)
    if d3 >= 0.0 and d4 <= d3: return b
    vc = d1*d4 - d3*d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        return _vadd(a,_vmul(ab,d1/max(1e-12,d1-d3)))
    cp = _vsub(point,c); d5, d6 = _dot(ab,cp), _dot(ac,cp)
    if d6 >= 0.0 and d5 <= d6: return c
    vb = d5*d2 - d1*d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        return _vadd(a,_vmul(ac,d2/max(1e-12,d2-d6)))
    va = d3*d6 - d5*d4
    if va <= 0.0 and (d4-d3) >= 0.0 and (d5-d6) >= 0.0:
        edge = _vsub(c,b); scale=(d4-d3)/max(1e-12,(d4-d3)+(d5-d6))
        return _vadd(b,_vmul(edge,scale))
    denom = 1.0/max(1e-12,va+vb+vc); v=vb*denom; w=vc*denom
    return _vadd(a,_vadd(_vmul(ab,v),_vmul(ac,w)))


def _oriented_outward_normal(a,b,c,center):
    normal = _normalize(_cross(_vsub(b,a),_vsub(c,a)))
    triangle_center = _vmul(_vadd(_vadd(a,b),c),1.0/3.0)
    if _dot(normal,_vsub(triangle_center,center)) < 0.0:
        normal = _vmul(normal,-1.0)
    return normal


@dataclass(frozen=True)
class TargetProjection:
    triangle_index: int
    point: Vector
    normal: Vector
    distance: float


def nearest_target_projection(point, surface, ambiguity_tolerance=1e-6):
    surface.validate()
    query = tuple(float(value) for value in point)
    best = None
    candidates = []
    for index, triangle in enumerate(surface.triangles):
        a,b,c = (surface.vertices[int(i)] for i in triangle)
        try: normal = _oriented_outward_normal(a,b,c,surface.center)
        except ValueError: continue
        closest = _closest_point_on_triangle(query,a,b,c)
        distance = _norm(_vsub(query,closest))
        if best is None or distance < best.distance:
            best = TargetProjection(index,closest,normal,distance); candidates=[best]
        elif abs(distance-best.distance) <= max(float(ambiguity_tolerance),best.distance*1e-9):
            candidates.append(TargetProjection(index,closest,normal,distance))
    if best is None:
        raise ValueError("target surface has no usable non-degenerate triangles")
    for candidate in candidates:
        if candidate.triangle_index != best.triangle_index and _dot(candidate.normal,best.normal) < 0.5:
            raise ValueError("target projection is ambiguous across opposing surface normals")
    return best


def signed_target_clearance(point, surface):
    projection = nearest_target_projection(point,surface)
    return _dot(_vsub(tuple(float(v) for v in point),projection.point),projection.normal)


@dataclass(frozen=True)
class ClearanceReport:
    minimum_signed_clearance: float
    point_index: int
    point: Vector
    projection: TargetProjection


def minimum_signed_clearance(points, surface):
    values = tuple(tuple(float(v) for v in point) for point in points)
    if not values:
        raise ValueError("clearance validation requires at least one garment sample point")
    best = None
    for index, point in enumerate(values):
        projection = nearest_target_projection(point,surface)
        signed = _dot(_vsub(point,projection.point),projection.normal)
        if not isfinite(signed):
            raise ValueError("target clearance became non-finite")
        report = ClearanceReport(signed,index,point,projection)
        if best is None or signed < best.minimum_signed_clearance: best = report
    return best


def average_point(points): return _average(points)

"""Deterministic, solver-neutral target-relative rigid garment placement.

The planner consumes only target bounds, local planar piece bounds, fitting metadata,
and a saved home placement. It does not import FreeCAD or create solver state.
"""
from dataclasses import dataclass
from math import acos, cos, radians, sin, sqrt
from typing import Tuple


Vector3 = Tuple[float, float, float]
Bounds3 = Tuple[float, float, float, float, float, float]
Bounds2 = Tuple[float, float, float, float]


@dataclass(frozen=True)
class PlacementPlan:
    position: Vector3
    rotation_axis: Vector3
    rotation_angle: float
    wrap_direction: str


VALID_WRAP_DIRECTIONS = ("front", "back", "left", "right")


def _normalize(v: Vector3) -> Vector3:
    length = sqrt(sum(float(c) * float(c) for c in v))
    if length <= 1e-12:
        raise ValueError("rotation axis must be non-zero")
    return tuple(float(c) / length for c in v)


def _quaternion(axis: Vector3, angle_degrees: float):
    ax = _normalize(axis)
    half = radians(float(angle_degrees)) * 0.5
    s = sin(half)
    return (cos(half), ax[0] * s, ax[1] * s, ax[2] * s)


def _quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _quat_conjugate(q):
    return (q[0], -q[1], -q[2], -q[3])


def _quat_rotate(q, vector: Vector3) -> Vector3:
    v = (0.0, vector[0], vector[1], vector[2])
    result = _quat_mul(_quat_mul(q, v), _quat_conjugate(q))
    return (result[1], result[2], result[3])


def _axis_angle_from_quaternion(q):
    w, x, y, z = q
    norm = sqrt(w * w + x * x + y * y + z * z)
    if norm <= 1e-12:
        raise ValueError("rotation quaternion is degenerate")
    w, x, y, z = (value / norm for value in q)
    w = abs(max(-1.0, min(1.0, w)))
    angle = 2.0 * acos(w)
    s = sqrt(max(0.0, 1.0 - w * w))
    if s <= 1e-9:
        return (0.0, 0.0, 1.0), 0.0
    return (x / s, y / s, z / s), angle * 180.0 / 3.141592653589793


def compose_side_rotation(wrap_direction: str):
    direction = str(wrap_direction).strip().lower()
    if direction not in VALID_WRAP_DIRECTIONS:
        raise ValueError("wrap direction must be front, back, left, or right")
    # Local pattern X stays lateral, local Y becomes vertical, and local Z
    # points away from the target on the requested side.
    if direction == "front":
        return _quaternion((1, 0, 0), 90.0)
    if direction == "back":
        return _quat_mul(_quaternion((0, 0, 1), 180.0), _quaternion((1, 0, 0), 90.0))
    if direction == "right":
        return _quat_mul(_quaternion((0, 0, 1), 90.0), _quaternion((1, 0, 0), 90.0))
    return _quat_mul(_quaternion((0, 0, 1), -90.0), _quaternion((1, 0, 0), 90.0))


def rotation_angle_between(
    home_axis: Vector3,
    home_angle: float,
    target_axis: Vector3,
    target_angle: float,
) -> float:
    home = _quaternion(home_axis, home_angle)
    target = _quaternion(target_axis, target_angle)
    relative = _quat_mul(target, _quat_conjugate(home))
    return _axis_angle_from_quaternion(relative)[1]


def plan_target_relative_placement(
    home_position: Vector3,
    home_rotation_axis: Vector3,
    home_rotation_angle: float,
    piece_bounds: Bounds2,
    target_bounds: Bounds3,
    wrap_direction: str,
    clearance: float,
    max_translation: float,
    max_rotation: float,
    anchor_position: Vector3 = None,
) -> PlacementPlan:
    direction = str(wrap_direction).strip().lower()
    if direction not in VALID_WRAP_DIRECTIONS:
        raise ValueError("wrap direction must be front, back, left, or right")
    if float(clearance) <= 0.0:
        raise ValueError("target placement clearance must be positive")
    if float(max_translation) <= 0.0 or float(max_rotation) <= 0.0:
        raise ValueError("target placement transform bounds must be positive")
    if len(piece_bounds) != 4 or len(target_bounds) != 6:
        raise ValueError("piece and target bounds have invalid dimensions")
    px_min, px_max, py_min, py_max = (float(value) for value in piece_bounds)
    tx_min, tx_max, ty_min, ty_max, tz_min, tz_max = (float(value) for value in target_bounds)
    if px_max <= px_min or py_max <= py_min:
        raise ValueError("piece bounds must have positive area")
    if tx_max <= tx_min or ty_max <= ty_min or tz_max <= tz_min:
        raise ValueError("target bounds must have positive extents")

    target_center = (
        0.5 * (tx_min + tx_max),
        0.5 * (ty_min + ty_max),
        0.5 * (tz_min + tz_max),
    )
    anchor = target_center if anchor_position is None else tuple(float(v) for v in anchor_position)
    if len(anchor) != 3:
        raise ValueError("anchor position must contain three coordinates")
    piece_center = (0.5 * (px_min + px_max), 0.5 * (py_min + py_max), 0.0)
    rotation = compose_side_rotation(direction)
    rotated_center = _quat_rotate(rotation, piece_center)

    if direction == "front":
        target_anchor = (anchor[0], ty_min - float(clearance), anchor[2])
    elif direction == "back":
        target_anchor = (anchor[0], ty_max + float(clearance), anchor[2])
    elif direction == "left":
        target_anchor = (tx_min - float(clearance), anchor[1], anchor[2])
    else:
        target_anchor = (tx_max + float(clearance), anchor[1], anchor[2])

    position = tuple(target_anchor[i] - rotated_center[i] for i in range(3))
    translation = sqrt(sum((position[i] - float(home_position[i])) ** 2 for i in range(3)))
    if translation > float(max_translation) + 1e-9:
        raise ValueError(
            "target placement translation %.6g mm exceeds configured bound %.6g mm"
            % (translation, float(max_translation))
        )
    axis, angle = _axis_angle_from_quaternion(rotation)
    rotation_delta = rotation_angle_between(
        home_rotation_axis, home_rotation_angle, axis, angle
    )
    if rotation_delta > float(max_rotation) + 1e-9:
        raise ValueError(
            "target placement rotation %.6g deg exceeds configured bound %.6g deg"
            % (rotation_delta, float(max_rotation))
        )
    return PlacementPlan(position, axis, angle, direction)


def target_bounds(vertices) -> Bounds3:
    points = tuple(tuple(float(c) for c in vertex) for vertex in vertices)
    if not points:
        raise ValueError("target collision surface has no vertices")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def piece_local_bounds(points) -> Bounds2:
    values = tuple(tuple(float(c) for c in point) for point in points)
    if not values:
        raise ValueError("pattern piece has no local geometry")
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return (min(xs), max(xs), min(ys), max(ys))

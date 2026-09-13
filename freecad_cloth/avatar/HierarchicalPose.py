"""Hierarchical MakeHuman arm posing using authored clavicle and arm weights."""
from __future__ import annotations

import json
import math

from freecad_cloth.avatar.HumanoidMesh import (
    MeshData,
    _axis_bounds,
    _estimate_rest_arm_angles,
    _estimate_shoulder_pivots,
    _is_default_measurement_shape,
    _lerp,
    _map_makehuman_axes,
    _measurement_profile,
    _normalize_fit_axes,
    _profile_scale,
    _reoriented_triangles,
    _smoothstep,
    ensure_makehuman_weights,
    load_makehuman_mesh,
)


def _group_weights(vertex_count: int, path: str | None = None):
    source = ensure_makehuman_weights(path)
    payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
    raw = payload["weights"]
    groups = {key: [0.0] * vertex_count for key in ("clavicle_l", "clavicle_r", "arm_l", "arm_r")}
    for bone_name, entries in raw.items():
        if not bone_name.endswith((".L", ".R")):
            continue
        base = bone_name[:-2]
        if base == "clavicle":
            group = "clavicle"
        elif base.startswith(("upperarm", "lowerarm", "wrist", "hand", "finger", "thumb")):
            group = "arm"
        else:
            continue
        side = "l" if bone_name.endswith(".L") else "r"
        target = groups[f"{group}_{side}"]
        for index, weight in entries:
            index = int(index)
            if 0 <= index < vertex_count:
                target[index] = min(1.0, target[index] + max(0.0, float(weight)))
    return {key: tuple(value) for key, value in groups.items()}


def _rotate_xz(point, pivot, radians):
    x, y, z = point
    dx = x - pivot[0]
    dz = z - pivot[1]
    c = math.cos(radians)
    s = math.sin(radians)
    return (pivot[0] + c * dx + s * dz, y, pivot[1] - s * dx + c * dz)


def _blend_weighted_pose(point, arm_weight, clavicle_weight, arm_pivot, clavicle_pivot, arm_radians, clavicle_radians):
    arm_weight = max(0.0, min(1.0, float(arm_weight)))
    clavicle_weight = max(0.0, min(1.0, float(clavicle_weight)))
    total = arm_weight + clavicle_weight
    if total > 1.0:
        arm_weight /= total
        clavicle_weight /= total
    arm_point = _rotate_xz(point, arm_pivot, arm_radians)
    clavicle_point = _rotate_xz(point, clavicle_pivot, clavicle_radians)
    torso_weight = max(0.0, 1.0 - arm_weight - clavicle_weight)
    return tuple(
        torso_weight * point[i] + arm_weight * arm_point[i] + clavicle_weight * clavicle_point[i]
        for i in range(3)
    )


def _estimate_clavicle_pivots(vertices, weights, shoulder_pivots, shoulder_z, height_mm):
    pivots = {}
    for side in (-1.0, 1.0):
        key = "clavicle_l" if side < 0 else "clavicle_r"
        candidates = [
            (side * x, z, weights[key][index])
            for index, (x, _y, z) in enumerate(vertices)
            if weights[key][index] >= 0.35 and 0.68 <= z / max(1.0, height_mm) <= 0.82
        ]
        if candidates:
            total = sum(weight for _x, _z, weight in candidates)
            cx = sum(x * weight for x, _z, weight in candidates) / max(1e-9, total)
            cz = sum(z * weight for _x, z, weight in candidates) / max(1e-9, total)
            target_x = min(cx, abs(shoulder_pivots[side]) * 0.92)
            target_x = max(abs(shoulder_pivots[side]) * 0.35, target_x)
            pivots[side] = (side * target_x, cz)
        else:
            pivots[side] = (side * abs(shoulder_pivots[side]) * 0.55, shoulder_z)
    return pivots


def build_hierarchical_avatar_mesh(parameters) -> MeshData:
    mesh = load_makehuman_mesh()
    source = _map_makehuman_axes(mesh.vertices)
    height_mm = float(parameters.measurement("height"))
    z0, z1 = _axis_bounds(source, 2)
    base_scale = height_mm / max(1e-9, z1 - z0)
    torso_profile = [(0.0, 1.0), (1.0, 1.0)] if _is_default_measurement_shape(parameters) else _measurement_profile(parameters)
    if _is_default_measurement_shape(parameters):
        shoulder_scale = 1.0
    else:
        from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS
        shoulder_scale = parameters.measurement("shoulder") / float(DEFAULT_MEASUREMENTS["shoulder"])
        shoulder_scale = max(0.80, min(1.25, shoulder_scale))
    skin_offset = float(parameters.skin_offset)
    fitted = []
    for x, y, z in source:
        torso_scale = _profile_scale(z, torso_profile)
        shoulder_blend = _smoothstep(0.67, 0.79, z)
        lateral_scale = _lerp(1.0, shoulder_scale, shoulder_blend)
        x_mm = x * base_scale * torso_scale * lateral_scale
        y_mm = y * base_scale * torso_scale
        radius = math.hypot(x_mm, y_mm)
        if radius > 1e-9 and skin_offset:
            x_mm += x_mm / radius * skin_offset
            y_mm += y_mm / radius * skin_offset
        fitted.append((x_mm, y_mm, z * height_mm))
    fitted = _normalize_fit_axes(tuple(fitted), parameters)
    weights = _group_weights(len(fitted))
    shoulder_half = float(parameters.measurement("shoulder")) / 2.0
    shoulder_z = height_mm * 0.76
    shoulder_pivots = _estimate_shoulder_pivots(fitted, shoulder_half, shoulder_z, height_mm)
    rest_angles = _estimate_rest_arm_angles(
        fitted, shoulder_pivots, shoulder_z, height_mm, (weights["arm_l"], weights["arm_r"])
    )
    clavicle_pivots = _estimate_clavicle_pivots(fitted, weights, shoulder_pivots, shoulder_z, height_mm)
    pose = parameters.pose
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(pose.preset, 12.0)
    left_angle = default_angle if pose.preset != "standing" and float(pose.left_arm_angle) == 12.0 else float(pose.left_arm_angle)
    right_angle = default_angle if pose.preset != "standing" and float(pose.right_arm_angle) == 12.0 else float(pose.right_arm_angle)
    posed = []
    for index, point in enumerate(fitted):
        side = -1.0 if point[0] < 0.0 else 1.0
        desired = left_angle if side < 0 else right_angle
        delta = side * math.radians(desired - rest_angles.get(side, 0.0))
        if abs(delta) <= 1e-9:
            posed.append(point)
            continue
        suffix = "l" if side < 0 else "r"
        posed.append(_blend_weighted_pose(
            point,
            weights[f"arm_{suffix}"][index],
            weights[f"clavicle_{suffix}"][index],
            (shoulder_pivots.get(side, side * shoulder_half), shoulder_z),
            clavicle_pivots.get(side, (side * shoulder_half * 0.55, shoulder_z)),
            delta,
            delta * 0.35,
        ))
    return MeshData(tuple(posed), _reoriented_triangles(mesh.triangles))


def generate_hierarchical_mesh(parameters):
    mesh = build_hierarchical_avatar_mesh(parameters)
    from freecad_cloth.avatar.AvatarModel import _landmarks
    return mesh.vertices, mesh.triangles, _landmarks(parameters)

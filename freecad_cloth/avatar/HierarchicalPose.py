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
    groups = {
        key: [0.0] * vertex_count
        for key in (
            "clavicle_l", "clavicle_r", "arm_l", "arm_r",
            "lowerarm_l", "lowerarm_r", "wrist_l", "wrist_r",
            "hand_l", "hand_r",
        )
    }
    for bone_name, entries in raw.items():
        if not bone_name.endswith((".L", ".R")):
            continue
        base = bone_name[:-2]
        if base == "clavicle":
            detail_group = "clavicle"
        elif base.startswith("upperarm"):
            detail_group = None
        elif base.startswith("lowerarm"):
            detail_group = "lowerarm"
        elif base.startswith("wrist"):
            detail_group = "wrist"
        elif base.startswith(("hand", "finger", "thumb")):
            detail_group = "hand"
        else:
            continue
        side = "l" if bone_name.endswith(".L") else "r"
        targets = [f"arm_{side}"] if detail_group != "clavicle" else []
        if detail_group:
            targets.append(f"{detail_group}_{side}")
            if detail_group == "clavicle":
                targets = [f"clavicle_{side}"]
        for index, weight in entries:
            index = int(index)
            if not (0 <= index < vertex_count):
                continue
            value = max(0.0, float(weight))
            for target_name in targets:
                groups[target_name][index] = min(1.0, groups[target_name][index] + value)
    return {key: tuple(value) for key, value in groups.items()}


def _weight_center_x(vertices, weights):
    total = sum(max(0.0, float(weight)) for weight in weights)
    if total <= 1e-12:
        return 0.0
    return sum(vertex[0] * max(0.0, float(weight)) for vertex, weight in zip(vertices, weights)) / total


def _weighted_center(vertices, weights, threshold=0.0):
    total = 0.0
    x = y = z = 0.0
    for vertex, weight in zip(vertices, weights):
        weight = max(0.0, float(weight))
        if weight <= threshold:
            continue
        x += vertex[0] * weight
        y += vertex[1] * weight
        z += vertex[2] * weight
        total += weight
    if total <= 1e-12:
        return None
    return (x / total, y / total, z / total)


def _weighted_distal_direction(vertices, weights, pivot, min_distance=1.0):
    """Find a distal hand axis while down-weighting wrist/base vertices.

    MakeHuman finger weights contain substantial mass on vertices close to the
    wrist. A plain weighted centroid therefore does not describe the direction
    of the actual fingers. Weight by squared distance from the wrist so distal
    finger vertices dominate the recovered hand axis.
    """
    total = 0.0
    dx = dz = 0.0
    for vertex, weight in zip(vertices, weights):
        weight = max(0.0, float(weight))
        if weight <= 1e-6:
            continue
        vx = vertex[0] - pivot[0]
        vz = vertex[2] - pivot[1]
        distance_sq = vx * vx + vz * vz
        if distance_sq < min_distance * min_distance:
            continue
        influence = weight * distance_sq
        dx += vx * influence
        dz += vz * influence
        total += influence
    if total <= 1e-12:
        return None
    return (dx / total, dz / total)


def _map_weight_groups_to_geometry(vertices, groups):
    """Map all MakeHuman .L/.R groups to the actual physical X sides."""
    mapped = dict(groups)
    for prefix in ("arm", "clavicle", "lowerarm", "wrist", "hand"):
        left_key = f"{prefix}_l"
        right_key = f"{prefix}_r"
        left_x = _weight_center_x(vertices, groups[left_key])
        right_x = _weight_center_x(vertices, groups[right_key])
        if left_x > right_x:
            mapped[left_key], mapped[right_key] = groups[right_key], groups[left_key]
    return mapped


def _rotate_xz(point, pivot, radians):
    x, y, z = point
    dx = x - pivot[0]
    dz = z - pivot[1]
    c = math.cos(radians)
    s = math.sin(radians)
    return (pivot[0] + c * dx + s * dz, y, pivot[1] - s * dx + c * dz)


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 1e-12:
        return None
    return tuple(component / length for component in vector)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _rotate_about_axis(point, pivot, axis, radians):
    axis = _normalize(axis)
    if axis is None:
        return point
    vector = tuple(point[i] - pivot[i] for i in range(3))
    c = math.cos(radians)
    s = math.sin(radians)
    cross = _cross(axis, vector)
    parallel = _dot(axis, vector)
    return tuple(
        pivot[i]
        + vector[i] * c
        + cross[i] * s
        + axis[i] * parallel * (1.0 - c)
        for i in range(3)
    )


def _hand_roll_angle(forearm_axis):
    """Return the roll that turns the authored palm edge into a front-facing palm.

    In the MakeHuman source pose the hand plane is carried by the forearm axis
    and the global Y direction, so its normal is axis × Y. The avatar views are
    front/back along Y; rotating that normal onto +Y removes the persistent
    90-degree edge-on palm seen in the front and side renders.
    """
    axis = _normalize(forearm_axis)
    if axis is None:
        return 0.0
    target_normal = (0.0, 1.0, 0.0)
    current_normal = _normalize(_cross(axis, target_normal))
    if current_normal is None:
        return 0.0
    sine = _dot(axis, _cross(current_normal, target_normal))
    cosine = max(-1.0, min(1.0, _dot(current_normal, target_normal)))
    return math.atan2(sine, cosine)


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


def _signed_angle_xz(dx, dz):
    return math.atan2(dz, dx)


def _shortest_angle(target, current):
    return (target - current + math.pi) % (2.0 * math.pi) - math.pi


def _straighten_hands(vertices, posed, weights):
    """Align the fingers with the forearm and roll the palms to face front/back."""
    result = list(posed)
    for side in (-1.0, 1.0):
        suffix = "l" if side < 0 else "r"
        wrist = _weighted_center(result, weights[f"wrist_{suffix}"], threshold=0.20)
        lowerarm = _weighted_center(result, weights[f"lowerarm_{suffix}"], threshold=0.20)
        if wrist is None or lowerarm is None:
            continue
        forearm_dx = wrist[0] - lowerarm[0]
        forearm_dz = wrist[2] - lowerarm[2]
        hand_direction = _weighted_distal_direction(
            result, weights[f"hand_{suffix}"], (wrist[0], wrist[2]), min_distance=4.0
        )
        if hand_direction is None:
            continue
        hand_dx, hand_dz = hand_direction
        if (forearm_dx * forearm_dx + forearm_dz * forearm_dz) < 1e-8:
            continue
        if (hand_dx * hand_dx + hand_dz * hand_dz) < 1e-8:
            continue
        correction = _shortest_angle(
            _signed_angle_xz(forearm_dx, forearm_dz),
            _signed_angle_xz(hand_dx, hand_dz),
        )
        correction = max(-math.radians(150.0), min(math.radians(150.0), correction))
        hand_roll = _hand_roll_angle((forearm_dx, 0.0, forearm_dz))
        hand_weights = weights[f"hand_{suffix}"]
        if abs(correction) > math.radians(0.5) or abs(hand_roll) > math.radians(0.5):
            pivot = wrist
            for index, point in enumerate(result):
                influence = max(0.0, min(1.0, float(hand_weights[index])))
                if influence <= 1e-6:
                    continue
                if abs(correction) > math.radians(0.5):
                    # _rotate_xz uses a clockwise-positive convention in the XZ plane,
                    # while correction is computed as target_angle - current_angle.
                    point = _rotate_xz(point, (pivot[0], pivot[2]), -correction)
                if abs(hand_roll) > math.radians(0.5):
                    point = _rotate_about_axis(
                        point,
                        pivot,
                        (forearm_dx, 0.0, forearm_dz),
                        hand_roll,
                    )
                result[index] = tuple(
                    posed[index][i] * (1.0 - influence) + point[i] * influence
                    for i in range(3)
                )
    return result


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
    weights = _map_weight_groups_to_geometry(fitted, _group_weights(len(fitted)))
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
    posed = _straighten_hands(fitted, posed, weights)
    return MeshData(tuple(posed), _reoriented_triangles(mesh.triangles))


def generate_hierarchical_mesh(parameters):
    mesh = build_hierarchical_avatar_mesh(parameters)
    from freecad_cloth.avatar.AvatarModel import _landmarks
    return mesh.vertices, mesh.triangles, _landmarks(parameters)

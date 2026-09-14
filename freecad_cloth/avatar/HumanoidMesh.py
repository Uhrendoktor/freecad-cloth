"""MakeHuman-backed humanoid mesh provider."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

MAKEHUMAN_COMMIT = "1f508f6083b2f823dab15de924b3bde72e08d77c9"
MAKEHUMAN_BASE_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    + MAKEHUMAN_COMMIT
    + "/makehuman/data/3dobjs/base.obj"
)
MAKEHUMAN_BASE_SHA256 = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
MAKEHUMAN_WEIGHTS_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    + MAKEHUMAN_COMMIT
    + "/makehuman/data/rigs/default_weights.mhw"
)
MAKEHUMAN_WEIGHTS_SIZE = 897521
MAKEHUMAN_SKELETON_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    + MAKEHUMAN_COMMIT
    + "/makehuman/data/rigs/default.mhskel"
)
MAKEHUMAN_SKELETON_SIZE = 117790
MAKEHUMAN_BODY_VERTEX_COUNT = 13380
CACHE_ENV = "FREECAD_CLOTH_AVATAR_MESH"
CACHE_DIR_ENV = "FREECAD_CLOTH_AVATAR_CACHE"
WEIGHTS_ENV = "FREECAD_CLOTH_AVATAR_WEIGHTS"
SKELETON_ENV = "FREECAD_CLOTH_AVATAR_SKELETON"
DEFAULT_CACHE_NAME = "makehuman-hm08-base.obj"
DEFAULT_WEIGHTS_NAME = "makehuman-default-weights.mhw"
DEFAULT_SKELETON_NAME = "makehuman-default.mhskel"


class HumanoidMeshError(RuntimeError):
    """Raised when the real humanoid mesh cannot be loaded or fitted."""


@dataclass(frozen=True)
class MeshData:
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]

    def validate(self):
        if len(self.vertices) < 3 or not self.triangles:
            raise HumanoidMeshError("humanoid mesh is empty")
        count = len(self.vertices)
        for tri in self.triangles:
            if len(tri) != 3 or any(i < 0 or i >= count for i in tri):
                raise HumanoidMeshError("humanoid mesh contains an invalid face")
        return self


def _cache_path(name: str, override_env: str) -> Path:
    configured = os.environ.get(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser() / name
    override = os.environ.get(override_env, "").strip()
    if override and override_env != CACHE_ENV:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "freecad-cloth" / name


def _default_cache_path() -> Path:
    override = os.environ.get(CACHE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return _cache_path(DEFAULT_CACHE_NAME, CACHE_ENV)


def _weights_cache_path() -> Path:
    return _cache_path(DEFAULT_WEIGHTS_NAME, WEIGHTS_ENV)


def _skeleton_cache_path() -> Path:
    return _cache_path(DEFAULT_SKELETON_NAME, SKELETON_ENV)


def _verified(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 1024:
        return False
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == MAKEHUMAN_BASE_SHA256
    except OSError:
        return False


def _verified_weights(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != MAKEHUMAN_WEIGHTS_SIZE:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
        return isinstance(payload.get("weights"), dict)
    except (OSError, UnicodeError, ValueError):
        return False


def _verified_skeleton(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != MAKEHUMAN_SKELETON_SIZE:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
        return isinstance(payload.get("bones"), dict) and isinstance(payload.get("joints"), dict)
    except (OSError, UnicodeError, ValueError):
        return False


def _download(url: str, destination: Path, verifier) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".makehuman-", suffix=destination.suffix, dir=str(destination.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            request = Request(url, headers={"User-Agent": "freecad-cloth/1"})
            with urlopen(request, timeout=60) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
        if not verifier(Path(temporary)):
            raise HumanoidMeshError("downloaded MakeHuman asset failed verification")
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def ensure_makehuman_base(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned HM08 base mesh, using an explicit local override when supplied."""
    override = os.environ.get(CACHE_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError("explicit humanoid mesh path does not exist: %s" % destination)
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError("%s points to a missing humanoid mesh: %s" % (CACHE_ENV, destination))
        return destination
    destination = _default_cache_path()
    if _verified(destination):
        return destination
    try:
        _download(MAKEHUMAN_BASE_URL, destination, _verified)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman HM08 base mesh; "
            "set %s to a local OBJ file or allow network access (%s)" % (CACHE_ENV, exc)
        ) from exc
    return destination


def ensure_makehuman_weights(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned MakeHuman default authored skinning weights."""
    override = os.environ.get(WEIGHTS_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError("explicit MakeHuman weights path does not exist: %s" % destination)
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError("%s points to missing MakeHuman weights: %s" % (WEIGHTS_ENV, destination))
        return destination
    destination = _weights_cache_path()
    if _verified_weights(destination):
        return destination
    try:
        _download(MAKEHUMAN_WEIGHTS_URL, destination, _verified_weights)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman default weights; "
            "set %s to a local MHW file or allow network access (%s)" % (WEIGHTS_ENV, exc)
        ) from exc
    return destination


def ensure_makehuman_skeleton(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned MakeHuman authored default skeleton."""
    override = os.environ.get(SKELETON_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError("explicit MakeHuman skeleton path does not exist: %s" % destination)
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError("%s points to missing MakeHuman skeleton: %s" % (SKELETON_ENV, destination))
        return destination
    destination = _skeleton_cache_path()
    if _verified_skeleton(destination):
        return destination
    try:
        _download(MAKEHUMAN_SKELETON_URL, destination, _verified_skeleton)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman default skeleton; "
            "set %s to a local MHSkel file or allow network access (%s)" % (SKELETON_ENV, exc)
        ) from exc
    return destination


def _parse_obj_vertices(text: str) -> tuple[tuple[float, float, float], ...]:
    vertices = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields[0] == "v" and len(fields) >= 4:
            vertices.append((float(fields[1]), float(fields[2]), float(fields[3])))
    return tuple(vertices)


def parse_obj(text: str) -> MeshData:
    """Parse HM08 and retain only its canonical visible body surface."""
    vertices = []
    triangles = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields[0] == "v" and len(fields) >= 4:
            vertices.append((float(fields[1]), float(fields[2]), float(fields[3])))
        elif fields[0] == "f" and len(fields) >= 4:
            indices = []
            for token in fields[1:]:
                index = int(token.split("/", 1)[0])
                index = len(vertices) + index if index < 0 else index - 1
                indices.append(index)
            for i in range(1, len(indices) - 1):
                triangles.append((indices[0], indices[i], indices[i + 1]))
    body_vertices = tuple(vertices[:MAKEHUMAN_BODY_VERTEX_COUNT])
    body_triangles = tuple(
        tri for tri in triangles if all(0 <= index < MAKEHUMAN_BODY_VERTEX_COUNT for index in tri)
    )
    return MeshData(body_vertices, body_triangles).validate()


@lru_cache(maxsize=4)
def _load_source_vertices(path: str | None = None) -> tuple[tuple[float, float, float], ...]:
    source = ensure_makehuman_base(path)
    try:
        return _parse_obj_vertices(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise HumanoidMeshError("unable to parse MakeHuman source vertices %s: %s" % (source, exc)) from exc


@lru_cache(maxsize=4)
def load_makehuman_mesh(path: str | None = None) -> MeshData:
    source = ensure_makehuman_base(path)
    try:
        return parse_obj(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, HumanoidMeshError) as exc:
        raise HumanoidMeshError("unable to parse MakeHuman base mesh %s: %s" % (source, exc)) from exc


@lru_cache(maxsize=4)
def load_makehuman_skeleton(path: str | None = None) -> dict:
    source = ensure_makehuman_skeleton(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
        if not isinstance(payload.get("bones"), dict) or not isinstance(payload.get("joints"), dict):
            raise HumanoidMeshError("MakeHuman skeleton is missing bones or joints")
        return payload
    except (OSError, UnicodeError, ValueError) as exc:
        raise HumanoidMeshError("unable to parse MakeHuman skeleton %s: %s" % (source, exc)) from exc


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _smoothstep(a, b, x):
    if a == b:
        return 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _axis_bounds(vertices, axis):
    values = [v[axis] for v in vertices]
    return min(values), max(values)


def _map_makehuman_axes(vertices):
    """Convert MakeHuman's Y-up coordinates to FreeCAD RH-Z-up coordinates."""
    ymin, ymax = _axis_bounds(vertices, 1)
    span = max(1e-9, ymax - ymin)
    return [(float(x), float(z), float(y - ymin) / span) for x, y, z in vertices]


def _reoriented_triangles(triangles):
    return tuple((int(a), int(c), int(b)) for a, b, c in triangles)


def _profile_scale(z, profile):
    for i in range(len(profile) - 1):
        z0, s0 = profile[i]
        z1, s1 = profile[i + 1]
        if z <= z1:
            return _lerp(s0, s1, _smoothstep(z0, z1, z))
    return profile[-1][1]


def _is_default_measurement_shape(parameters) -> bool:
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    return all(
        math.isclose(parameters.measurement(name), value, rel_tol=0.0, abs_tol=1e-9)
        for name, value in DEFAULT_MEASUREMENTS.items()
    )


def _measurement_profile(parameters):
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    bands = (("hip", 0.50), ("high_hip", 0.54), ("waist", 0.58), ("underbust", 0.64), ("chest", 0.69))
    profile = [(0.42, 1.0)]
    for name, z in bands:
        ratio = parameters.measurement(name) / float(DEFAULT_MEASUREMENTS[name])
        profile.append((z, max(0.75, min(1.35, ratio))))
    profile.extend(((0.75, profile[-1][1]), (1.0, profile[-1][1])))
    return profile


def _horizontal_scales(vertices, parameters):
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    x_min, x_max = _axis_bounds(vertices, 0)
    y_min, y_max = _axis_bounds(vertices, 1)
    x_span = x_max - x_min
    y_span = y_max - y_min
    if x_span <= 1e-9 or y_span <= 1e-9:
        return 1.0, 1.0
    shoulder = float(parameters.measurement("shoulder"))
    upper_arm = float(parameters.measurement("upper_arm"))
    chest = float(parameters.measurement("chest"))
    default_upper_arm = float(DEFAULT_MEASUREMENTS["upper_arm"])
    default_chest = float(DEFAULT_MEASUREMENTS["chest"])
    target_width = shoulder + 1.5 * upper_arm
    target_depth = chest / math.pi
    target_width *= 1.0 + 0.05 * max(0.0, (upper_arm / default_upper_arm) - 1.0)
    target_depth *= 1.0 + 0.05 * max(0.0, (chest / default_chest) - 1.0)
    return target_width / x_span, target_depth / y_span


def _normalize_fit_axes(vertices, parameters):
    scale_x, scale_y = _horizontal_scales(vertices, parameters)
    return tuple((x * scale_x, y * scale_y, z) for x, y, z in vertices)


def _estimate_shoulder_pivots(vertices, shoulder_half, shoulder_z, height_mm):
    pivots = {}
    for side in (-1.0, 1.0):
        lateral = sorted(
            side * x
            for x, _y, z in vertices
            if side * x >= shoulder_half * 0.55 and 0.68 <= z / max(1.0, height_mm) <= 0.82
        )
        if not lateral:
            pivots[side] = side * shoulder_half
            continue
        count = max(1, int(math.ceil(len(lateral) * 0.15)))
        medial = sum(lateral[:count]) / float(count)
        medial = max(shoulder_half * 0.70, min(shoulder_half * 0.99, medial))
        pivots[side] = side * medial
    return pivots


def _estimate_rest_arm_angles(vertices, shoulder_pivots, shoulder_z, height_mm, arm_weights=None):
    result = {}
    for side_index, side in enumerate((-1.0, 1.0)):
        pivot_x = shoulder_pivots.get(side, side * 0.0)
        weights = None if arm_weights is None else arm_weights[side_index]
        samples = []
        for index, (x, _y, z) in enumerate(vertices):
            if side * x <= side * pivot_x * 1.05 or not 0.50 <= z / max(1.0, height_mm) <= 0.78:
                continue
            influence = 1.0 if weights is None else weights[index]
            if influence <= 0.05:
                continue
            samples.append((x, z, influence))
        if not samples:
            result[side] = 0.0
            continue
        weighted_x = weighted_z = total = 0.0
        for x, z, influence in samples:
            weight = influence * max(0.1, side * (x - pivot_x))
            weighted_x += x * weight
            weighted_z += z * weight
            total += weight
        center_x = weighted_x / total
        center_z = weighted_z / total
        result[side] = math.degrees(math.atan2(max(0.0, shoulder_z - center_z), max(1e-6, side * (center_x - pivot_x))))
    return result


def _is_arm_bone(name: str, side: str) -> bool:
    if not name.endswith(side):
        return False
    base = name[:-2]
    return base.startswith(("upperarm", "lowerarm", "wrist", "hand", "finger", "thumb"))


@lru_cache(maxsize=4)
def load_makehuman_arm_weights(vertex_count: int, path: str | None = None) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Load MakeHuman-authored weights for the complete upper-arm-to-finger chain."""
    source = ensure_makehuman_weights(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
        raw = payload["weights"]
        left = [0.0] * vertex_count
        right = [0.0] * vertex_count
        for bone_name, entries in raw.items():
            if _is_arm_bone(bone_name, ".L"):
                target = left
            elif _is_arm_bone(bone_name, ".R"):
                target = right
            else:
                continue
            for index, weight in entries:
                index = int(index)
                if 0 <= index < vertex_count:
                    target[index] = min(1.0, target[index] + max(0.0, float(weight)))
        return tuple(left), tuple(right)
    except (KeyError, OSError, UnicodeError, ValueError, TypeError) as exc:
        raise HumanoidMeshError("unable to parse MakeHuman arm weights %s: %s" % (source, exc)) from exc


def _map_arm_weights_to_physical_sides(vertices, weights):
    left, right = weights
    left_total = sum(max(0.0, w) for w in left)
    right_total = sum(max(0.0, w) for w in right)
    if left_total <= 1e-12 or right_total <= 1e-12:
        return weights
    left_center = sum(v[0] * w for v, w in zip(vertices, left)) / left_total
    right_center = sum(v[0] * w for v, w in zip(vertices, right)) / right_total
    return (right, left) if left_center > right_center else (left, right)


def _joint_point(source_vertices, indices):
    points = [source_vertices[int(index)] for index in indices if 0 <= int(index) < len(source_vertices)]
    if not points:
        raise HumanoidMeshError("MakeHuman skeleton references missing joint vertices")
    count = float(len(points))
    return tuple(sum(point[axis] for point in points) / count for axis in range(3))


def _bone_source_endpoints(source_vertices, skeleton, bone_name):
    bone = skeleton["bones"].get(bone_name)
    if not bone:
        raise HumanoidMeshError("MakeHuman skeleton has no bone %s" % bone_name)
    return (
        _joint_point(source_vertices, skeleton["joints"][bone["head"]]),
        _joint_point(source_vertices, skeleton["joints"][bone["tail"]]),
    )


def _map_bones_to_physical_sides(source_vertices, skeleton, mapped_transform):
    result = {}
    for logical_side, suffix in ((-1.0, ".L"), (1.0, ".R")):
        shoulder = _bone_source_endpoints(source_vertices, skeleton, "upperarm01" + suffix)
        wrist = _bone_source_endpoints(source_vertices, skeleton, "wrist" + suffix)
        result[logical_side] = {"shoulder": tuple(mapped_transform(p) for p in shoulder), "wrist": tuple(mapped_transform(p) for p in wrist)}
    left_x = result[-1.0]["shoulder"][0][0]
    right_x = result[1.0]["shoulder"][0][0]
    if left_x > right_x:
        result[-1.0], result[1.0] = result[1.0], result[-1.0]
    return result


def _rotate_xz(point, pivot, radians):
    x, y, z = point
    dx = x - pivot[0]
    dz = z - pivot[1]
    c = math.cos(radians)
    s = math.sin(radians)
    return (pivot[0] + c * dx + s * dz, y, pivot[1] - s * dx + c * dz)


def _arm_pose_weight(x, z, shoulder_pivot_x, height_mm, source_weight=None):
    """Compatibility helper; production posing uses only authored weights."""
    if source_weight is not None:
        return max(0.0, min(1.0, float(source_weight)))
    pivot = abs(shoulder_pivot_x)
    lateral = _smoothstep(pivot * 0.98, pivot * 1.12, abs(x))
    nz = z / max(1.0, height_mm)
    vertical = _smoothstep(0.56, 0.62, nz) * (1.0 - _smoothstep(0.88, 0.96, nz))
    return lateral * vertical


def _fit_legacy_geometry(mesh: MeshData, parameters) -> MeshData:
    source = _map_makehuman_axes(mesh.vertices)
    height_mm = float(parameters.measurement("height"))
    z0, z1 = _axis_bounds(source, 2)
    height_unit = max(1e-9, z1 - z0)
    base_scale = height_mm / height_unit
    torso_profile = [(0.0, 1.0), (1.0, 1.0)] if _is_default_measurement_shape(parameters) else _measurement_profile(parameters)
    if _is_default_measurement_shape(parameters):
        shoulder_scale = 1.0
    else:
        from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS
        shoulder_scale = max(0.80, min(1.25, parameters.measurement("shoulder") / float(DEFAULT_MEASUREMENTS["shoulder"])))
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
    return MeshData(tuple(fitted), _reoriented_triangles(mesh.triangles))


def _fit_source_coordinates(source_vertices, parameters, apply_skin_offset):
    body = tuple(source_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT])
    if len(body) != MAKEHUMAN_BODY_VERTEX_COUNT:
        raise HumanoidMeshError("MakeHuman source does not contain the HM08 visible body")
    ymin, ymax = _axis_bounds(body, 1)
    y_span = max(1e-9, ymax - ymin)
    height_mm = float(parameters.measurement("height"))
    base_scale = height_mm / y_span
    torso_profile = [(0.0, 1.0), (1.0, 1.0)] if _is_default_measurement_shape(parameters) else _measurement_profile(parameters)
    if _is_default_measurement_shape(parameters):
        shoulder_scale = 1.0
    else:
        from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS
        shoulder_scale = max(0.80, min(1.25, parameters.measurement("shoulder") / float(DEFAULT_MEASUREMENTS["shoulder"])))

    def mapped(point):
        x, y, z = point
        return float(x), float(z), float(y - ymin) / y_span

    def fit_point(point, skin_offset):
        x, y, z = mapped(point)
        torso_scale = _profile_scale(z, torso_profile)
        shoulder_blend = _smoothstep(0.67, 0.79, z)
        lateral_scale = _lerp(1.0, shoulder_scale, shoulder_blend)
        x_mm = x * base_scale * torso_scale * lateral_scale
        y_mm = y * base_scale * torso_scale
        radius = math.hypot(x_mm, y_mm)
        if radius > 1e-9 and skin_offset:
            x_mm += x_mm / radius * skin_offset
            y_mm += y_mm / radius * skin_offset
        return (x_mm, y_mm, z * height_mm)

    visible = tuple(fit_point(point, float(parameters.skin_offset) if apply_skin_offset else 0.0) for point in body)
    scale_x, scale_y = _horizontal_scales(visible, parameters)
    visible = tuple((x * scale_x, y * scale_y, z) for x, y, z in visible)
    helpers = tuple(fit_point(point, 0.0) for point in source_vertices)
    helpers = tuple((x * scale_x, y * scale_y, z) for x, y, z in helpers)
    return visible, helpers


def _pose_with_authored_rig(mesh: MeshData, parameters, arm_weights) -> MeshData:
    source_path = str(ensure_makehuman_base())
    source_vertices = _load_source_vertices(source_path)
    skeleton = load_makehuman_skeleton()
    fitted, fitted_source = _fit_source_coordinates(source_vertices, parameters, apply_skin_offset=True)
    # Build a source->fitted mapper from the already fitted helper cloud. The
    # skeleton is authored in the same HM08 vertex space, so this is exact for
    # the corresponding helper vertices used by the rig.
    source_ymin, source_ymax = _axis_bounds(source_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT], 1)
    source_yspan = max(1e-9, source_ymax - source_ymin)
    height_mm = float(parameters.measurement("height"))
    base_scale = height_mm / source_yspan
    torso_profile = [(0.0, 1.0), (1.0, 1.0)] if _is_default_measurement_shape(parameters) else _measurement_profile(parameters)
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS
    shoulder_scale = 1.0 if _is_default_measurement_shape(parameters) else max(0.80, min(1.25, parameters.measurement("shoulder") / float(DEFAULT_MEASUREMENTS["shoulder"])))
    scale_x, scale_y = _horizontal_scales(fitted, parameters)

    def transform_source(point):
        x, y, z = point
        z_norm = (y - source_ymin) / source_yspan
        torso_scale = _profile_scale(z_norm, torso_profile)
        shoulder_blend = _smoothstep(0.67, 0.79, z_norm)
        lateral_scale = _lerp(1.0, shoulder_scale, shoulder_blend)
        x_mm = x * base_scale * torso_scale * lateral_scale
        y_mm = z * base_scale * torso_scale
        return (x_mm * scale_x, y_mm * scale_y, z_norm * height_mm)

    bones = _map_bones_to_physical_sides(source_vertices, skeleton, transform_source)
    physical_weights = _map_arm_weights_to_physical_sides(fitted, arm_weights)
    pose = parameters.pose
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(pose.preset, 12.0)
    left_angle = default_angle if float(pose.left_arm_angle) == 12.0 and pose.preset != "standing" else float(pose.left_arm_angle)
    right_angle = default_angle if float(pose.right_arm_angle) == 12.0 and pose.preset != "standing" else float(pose.right_arm_angle)

    deltas = {}
    for side, desired in ((-1.0, left_angle), (1.0, right_angle)):
        shoulder_head = bones[side]["shoulder"][0]
        wrist_head = bones[side]["wrist"][0]
        radial = side * (wrist_head[0] - shoulder_head[0])
        downward = shoulder_head[2] - wrist_head[2]
        rest_angle = math.degrees(math.atan2(downward, max(1e-9, radial)))
        deltas[side] = side * math.radians(desired - rest_angle)

    posed = []
    for index, point in enumerate(fitted):
        side = -1.0 if point[0] < 0.0 else 1.0
        influence = max(0.0, min(1.0, float(physical_weights[0 if side < 0 else 1][index])))
        if influence <= 1e-9:
            posed.append(point)
            continue
        pivot = bones[side]["shoulder"][0]
        rotated = _rotate_xz(point, (pivot[0], pivot[2]), deltas[side])
        posed.append(tuple(point[axis] + influence * (rotated[axis] - point[axis]) for axis in range(3)))
    return MeshData(tuple(posed), _reoriented_triangles(mesh.triangles))


def fit_makehuman_mesh(mesh: MeshData, parameters, arm_weights=None) -> MeshData:
    """Fit HM08 and pose the complete arm chain with MakeHuman's authored rig and weights."""
    mesh.validate()
    if len(mesh.vertices) != MAKEHUMAN_BODY_VERTEX_COUNT or arm_weights is None:
        return _fit_legacy_geometry(mesh, parameters)
    try:
        return _pose_with_authored_rig(mesh, parameters, arm_weights)
    except HumanoidMeshError:
        raise
    except (KeyError, OSError, UnicodeError, ValueError, TypeError) as exc:
        raise HumanoidMeshError("unable to apply the pinned MakeHuman arm rig: %s" % exc) from exc


def build_humanoid_mesh(parameters, source_path=None) -> MeshData:
    source = load_makehuman_mesh(str(source_path) if source_path is not None else None)
    if source_path is not None:
        return fit_makehuman_mesh(source, parameters, arm_weights=None)
    weights = load_makehuman_arm_weights(len(source.vertices))
    return fit_makehuman_mesh(source, parameters, arm_weights=weights)

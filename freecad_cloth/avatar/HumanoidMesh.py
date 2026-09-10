"""MakeHuman-backed humanoid mesh provider.

The avatar is a real polygonal human base mesh rather than a collection of
FreeCAD primitives. The pinned MakeHuman HM08 base mesh is fetched lazily and
cached locally, then fitted into the Cloth millimetre coordinate system.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
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
MAKEHUMAN_BODY_VERTEX_COUNT = 13380
CACHE_ENV = "FREECAD_CLOTH_AVATAR_MESH"
CACHE_DIR_ENV = "FREECAD_CLOTH_AVATAR_CACHE"
DEFAULT_CACHE_NAME = "makehuman-hm08-base.obj"


class HumanoidMeshError(RuntimeError):
    """Raised when the real humanoid asset cannot be loaded or fitted."""


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


def _default_cache_path() -> Path:
    configured = os.environ.get(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser() / DEFAULT_CACHE_NAME
    return Path.home() / ".cache" / "freecad-cloth" / DEFAULT_CACHE_NAME


def _verified(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 1024:
        return False
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == MAKEHUMAN_BASE_SHA256
    except OSError:
        return False


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".makehuman-", suffix=".obj", dir=str(destination.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            request = Request(url, headers={"User-Agent": "freecad-cloth/1"})
            with urlopen(request, timeout=60) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
        if not _verified(Path(temporary)):
            raise HumanoidMeshError("downloaded MakeHuman base mesh failed SHA-256 verification")
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def ensure_makehuman_base(path: str | os.PathLike[str] | None = None) -> Path:
    """Return a real human OBJ, using an explicit local override when supplied."""
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
        _download(MAKEHUMAN_BASE_URL, destination)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman HM08 base mesh; "
            "set %s to a local OBJ file or allow network access (%s)" % (CACHE_ENV, exc)
        ) from exc
    return destination


def parse_obj(text: str) -> MeshData:
    """Parse HM08 and retain only its canonical visible body surface.

    HM08 stores the visible body first (vertices 0..13379), followed by helper
    geometry used internally by MakeHuman for joints, clothing and weighting.
    The helpers must not become visible FreeCAD anatomy.
    """
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
        tri for tri in triangles
        if all(0 <= index < MAKEHUMAN_BODY_VERTEX_COUNT for index in tri)
    )
    return MeshData(body_vertices, body_triangles).validate()


@lru_cache(maxsize=4)
def load_makehuman_mesh(path: str | None = None) -> MeshData:
    source = ensure_makehuman_base(path)
    try:
        return parse_obj(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, HumanoidMeshError) as exc:
        raise HumanoidMeshError("unable to parse MakeHuman base mesh %s: %s" % (source, exc)) from exc


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
    """Map the dominant source height axis into FreeCAD's RH-Z-up frame.

    MakeHuman exports are normally Y-up/Z-depth, but OBJ assets can be
    transformed by upstream tooling. The humanoid's anatomical height is the
    only source extent expected to dominate the other two extents, so infer it
    from the measured spans and then keep the larger remaining span as body
    width and the smaller as front/back depth. For the canonical Y-up/Z-depth
    source this reduces to X, -Z, Y as used by the MakeHuman ecosystem.
    """
    spans = tuple(_axis_bounds(vertices, axis)[1] - _axis_bounds(vertices, axis)[0] for axis in range(3))
    height_axis = max(range(3), key=lambda axis: spans[axis])
    remaining = [axis for axis in range(3) if axis != height_axis]
    width_axis, depth_axis = sorted(remaining, key=lambda axis: spans[axis], reverse=True)
    bounds = {axis: _axis_bounds(vertices, axis) for axis in range(3)}
    hmin, hmax = bounds[height_axis]
    hspan = max(1e-9, hmax - hmin)

    def coordinate(vertex, axis):
        return float(vertex[axis])

    # Preserve a conventional right-handed frame while allowing mirrored CAD
    # assets to retain their source handedness in the width/depth axes.
    output = []
    for vertex in vertices:
        width = coordinate(vertex, width_axis)
        depth = -coordinate(vertex, depth_axis)
        height = (coordinate(vertex, height_axis) - hmin) / hspan
        output.append((width, depth, height))
    return output


def _profile_scale(z, profile):
    for i in range(len(profile) - 1):
        z0, s0 = profile[i]
        z1, s1 = profile[i + 1]
        if z <= z1:
            return _lerp(s0, s1, _smoothstep(z0, z1, z))
    return profile[-1][1]


def _is_default_measurement_shape(parameters) -> bool:
    """Return whether the authoritative dimensions are the canonical defaults."""
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    return all(
        math.isclose(parameters.measurement(name), value, rel_tol=0.0, abs_tol=1e-9)
        for name, value in DEFAULT_MEASUREMENTS.items()
    )


def _measurement_profile(parameters):
    """Return proportional changes relative to the canonical mannequin dimensions."""
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    bands = (
        ("hip", 0.50),
        ("high_hip", 0.54),
        ("waist", 0.58),
        ("underbust", 0.64),
        ("chest", 0.69),
    )
    profile = [(0.42, 1.0)]
    for name, z in bands:
        ratio = parameters.measurement(name) / float(DEFAULT_MEASUREMENTS[name])
        profile.append((z, max(0.75, min(1.35, ratio))))
    profile.extend(((0.75, profile[-1][1]), (1.0, profile[-1][1])))
    return profile


def _estimate_rest_arm_angles(vertices, shoulder_half, shoulder_z, height_mm):
    """Estimate each HM08 arm's unposed angle from its actual A-pose geometry."""
    result = {}
    for side in (-1.0, 1.0):
        samples = [
            (x, z)
            for x, _, z in vertices
            if side * x > shoulder_half * 1.05 and 0.50 <= z / max(1.0, height_mm) <= 0.78
        ]
        if not samples:
            result[side] = 0.0
            continue
        weighted_x = 0.0
        weighted_z = 0.0
        total = 0.0
        for x, z in samples:
            weight = max(0.1, side * x - shoulder_half)
            weighted_x += x * weight
            weighted_z += z * weight
            total += weight
        center_x = weighted_x / total
        center_z = weighted_z / total
        radial_x = max(1e-6, side * (center_x - side * shoulder_half))
        downward = max(0.0, shoulder_z - center_z)
        result[side] = math.degrees(math.atan2(downward, radial_x))
    return result


def _arm_pose_weight(x, z, shoulder_half, height_mm):
    """Return a smooth 0..1 influence that keeps the whole lateral arm attached."""
    lateral = _smoothstep(shoulder_half * 0.88, shoulder_half * 1.02, abs(x))
    nz = z / max(1.0, height_mm)
    vertical = _smoothstep(0.34, 0.40, nz) * (1.0 - _smoothstep(0.88, 0.96, nz))
    return lateral * vertical


def fit_makehuman_mesh(mesh: MeshData, parameters) -> MeshData:
    """Fit HM08 while preserving its canonical silhouette and articulated limbs.

    The default mannequin receives only global height normalization. Body shape
    changes remain bounded proportional deltas, and arm posing is expressed as a
    rotation from the mesh's native A-pose instead of assuming a horizontal rest
    pose. A smooth arm influence prevents triangles, hands and fingers from being
    split by a hard spatial cutoff.
    """
    mesh.validate()
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
        shoulder_ratio = parameters.measurement("shoulder") / float(DEFAULT_MEASUREMENTS["shoulder"])
        shoulder_scale = max(0.80, min(1.25, shoulder_ratio))

    skin_offset = float(parameters.skin_offset)
    fitted = []
    shoulder_half = float(parameters.measurement("shoulder")) / 2.0
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

    pose = parameters.pose
    shoulder_z = height_mm * 0.76
    rest_angles = _estimate_rest_arm_angles(fitted, shoulder_half, shoulder_z, height_mm)
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(pose.preset, 12.0)
    left_angle = default_angle if pose.preset != "standing" and float(pose.left_arm_angle) == 12.0 else float(pose.left_arm_angle)
    right_angle = default_angle if pose.preset != "standing" and float(pose.right_arm_angle) == 12.0 else float(pose.right_arm_angle)
    posed = []
    for x, y, z in fitted:
        weight = _arm_pose_weight(x, z, shoulder_half, height_mm)
        if weight <= 1e-9:
            posed.append((x, y, z))
            continue
        side = -1.0 if x < 0.0 else 1.0
        desired = left_angle if side < 0 else right_angle
        delta = desired - rest_angles.get(side, 0.0)
        if abs(delta) <= 1e-9:
            posed.append((x, y, z))
            continue
        radians = side * math.radians(delta) * weight
        pivot_x = side * shoulder_half
        dx = x - pivot_x
        dz = z - shoulder_z
        x, z = (
            pivot_x + math.cos(radians) * dx + math.sin(radians) * dz,
            shoulder_z - math.sin(radians) * dx + math.cos(radians) * dz,
        )
        posed.append((x, y, z))
    return MeshData(tuple(posed), mesh.triangles)


def build_humanoid_mesh(parameters, source_path=None) -> MeshData:
    """Load, fit and return the real MakeHuman mannequin mesh for Cloth."""
    return fit_makehuman_mesh(load_makehuman_mesh(str(source_path) if source_path is not None else None), parameters)

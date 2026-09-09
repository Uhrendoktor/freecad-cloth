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

MAKEHUMAN_COMMIT = "1f508f6083b2f823dab15de924b3bde72e08d77c"
MAKEHUMAN_BASE_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    + MAKEHUMAN_COMMIT
    + "/makehuman/data/3dobjs/base.obj"
)
MAKEHUMAN_BASE_SHA256 = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
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
        if len(self.vertices) < 3 or len(self.triangles) < 1:
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
    """Parse Wavefront vertices/faces; triangulate quads and n-gons."""
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
    return MeshData(tuple(vertices), tuple(triangles)).validate()


@lru_cache(maxsize=4)
def load_makehuman_mesh(path: str | None = None) -> MeshData:
    source = ensure_makehuman_base(path)
    try:
        return parse_obj(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, HumanoidMeshError) as exc:
        raise HumanoidMeshError("unable to parse MakeHuman base mesh %s: %s" % (source, exc)) from exc


def _percentile(values, fraction):
    values = sorted(values)
    if not values:
        return 0.0
    position = (len(values) - 1) * fraction
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return float(values[low])
    weight = position - low
    return float(values[low] * (1.0 - weight) + values[high] * weight)


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
    """Convert MakeHuman's Y-up decimetre coordinates to RH-Z-up millimetres."""
    ymin, ymax = _axis_bounds(vertices, 1)
    span = max(1e-9, ymax - ymin)
    return [(float(x), float(z), float(y - ymin) / span) for x, y, z in vertices]


def _profile_scale(z, profile):
    for i in range(len(profile) - 1):
        z0, s0 = profile[i]
        z1, s1 = profile[i + 1]
        if z <= z1:
            return _lerp(s0, s1, _smoothstep(z0, z1, z))
    return profile[-1][1]


def fit_makehuman_mesh(mesh: MeshData, parameters) -> MeshData:
    """Fit the real base mesh to Cloth measurements while retaining topology."""
    mesh.validate()
    source = _map_makehuman_axes(mesh.vertices)
    max_x = max(abs(v[0]) for v in source) or 1.0

    height_mm = float(parameters.measurement("height"))
    z0, z1 = _axis_bounds(source, 2)
    height_unit = max(1e-9, z1 - z0)
    base_scale = height_mm / height_unit

    torso_vertices = [v for v in source if abs(v[0]) <= max_x * 0.38] or source
    bands = {"hip": 0.43, "high_hip": 0.48, "waist": 0.56, "underbust": 0.62, "chest": 0.69, "shoulder": 0.75}
    target_circumferences = {name: float(parameters.measurement(name)) for name in bands}
    base_radius = {}
    for name, z in bands.items():
        samples = [math.hypot(v[0], v[1]) for v in torso_vertices if abs(v[2] - z) < 0.025]
        base_radius[name] = max(1e-5, _percentile(samples, 0.75) if samples else max_x * 0.30)

    target_radius = {name: value / (2.0 * math.pi * base_scale) for name, value in target_circumferences.items()}
    profile_points = [
        (0.35, target_radius["hip"] / base_radius["hip"]),
        (0.48, target_radius["high_hip"] / base_radius["high_hip"]),
        (0.56, target_radius["waist"] / base_radius["waist"]),
        (0.62, target_radius["underbust"] / base_radius["underbust"]),
        (0.69, target_radius["chest"] / base_radius["chest"]),
        (0.77, target_radius["shoulder"] / base_radius["shoulder"]),
        (1.0, target_radius["shoulder"] / base_radius["shoulder"]),
    ]

    fitted = []
    for x, y, z in source:
        radial = _profile_scale(z, profile_points)
        fitted.append((x * base_scale * radial, y * base_scale * radial, z * height_mm))

    pose = parameters.pose
    shoulder_z = height_mm * 0.76
    shoulder_half = float(parameters.measurement("shoulder")) / 2.0
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(pose.preset, 12.0)
    left_angle = default_angle if pose.preset != "standing" and float(pose.left_arm_angle) == 12.0 else float(pose.left_arm_angle)
    right_angle = default_angle if pose.preset != "standing" and float(pose.right_arm_angle) == 12.0 else float(pose.right_arm_angle)
    posed = []
    body_half = max(1.0, shoulder_half * 0.75)
    for x, y, z in fitted:
        nz = z / max(1.0, height_mm)
        if 0.58 <= nz <= 0.90 and abs(x) > body_half:
            side = -1.0 if x < 0.0 else 1.0
            angle = left_angle if side < 0 else right_angle
            if angle:
                radians = side * math.radians(angle)
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
    """Load, fit and return the real MakeHuman mesh for Cloth."""
    return fit_makehuman_mesh(load_makehuman_mesh(str(source_path) if source_path is not None else None), parameters)

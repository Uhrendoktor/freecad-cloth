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
    """Parse Wavefront vertices/faces; triangulate quads and n-gons.

    Keep the source topology intact.  The MakeHuman base mesh is one canonical
    surface; choosing an arbitrary connected component can silently discard
    legitimate anatomy or produce a visibly incomplete mannequin.
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
    return MeshData(tuple(vertices), tuple(triangles)).validate()


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
    """Convert MakeHuman's Y-up coordinates to RH-Z-up normalized coordinates."""
    ymin, ymax = _axis_bounds(vertices, 1)
    span = max(1e-9, ymax - ymin)
    return [(float(x), float(-z), float(y - ymin) / span) for x, y, z in vertices]


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


def fit_makehuman_mesh(mesh: MeshData, parameters) -> MeshData:
    """Fit HM08 without rewriting its canonical silhouette.

    The default mannequin gets one global height normalization and the selected
    pose.  Custom measurements are applied only as proportional deltas from that
    canonical shape, avoiding a five-band reconstruction of the human body.
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
    body_half = float(parameters.measurement("shoulder")) * 0.36
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
    shoulder_half = float(parameters.measurement("shoulder")) / 2.0
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(pose.preset, 12.0)
    left_angle = default_angle if pose.preset != "standing" and float(pose.left_arm_angle) == 12.0 else float(pose.left_arm_angle)
    right_angle = default_angle if pose.preset != "standing" and float(pose.right_arm_angle) == 12.0 else float(pose.right_arm_angle)
    posed = []
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
    """Load, fit and return the real MakeHuman mannequin mesh for Cloth."""
    return fit_makehuman_mesh(load_makehuman_mesh(str(source_path) if source_path is not None else None), parameters)

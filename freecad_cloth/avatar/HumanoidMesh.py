"""MakeHuman-backed humanoid mesh provider.

The avatar is a real polygonal human base mesh rather than a collection of
FreeCAD primitives. The pinned MakeHuman HM08 base mesh is fetched lazily and
cached locally, then fitted into the Cloth millimetre coordinate system.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Self, TypedDict, cast
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


if TYPE_CHECKING:
    from freecad_cloth.avatar.AvatarModel import AvatarParameters


Point = tuple[float, float, float]
Triangle = tuple[int, int, int]


class BoneData(TypedDict):
    """Minimal authored bone fields used by the avatar fitting pipeline."""

    head: str
    tail: str


class SkeletonData(TypedDict):
    """Authored MakeHuman joint index lists and their referencing bones."""

    bones: dict[str, BoneData]
    joints: dict[str, list[int]]


class HumanoidMeshError(RuntimeError):
    """Raised when the real humanoid mesh cannot be loaded or fitted."""


@dataclass(frozen=True)
class MeshData:
    """Public data model or service class for MeshData."""

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]

    def validate(self) -> Self:
        """Validate this value and raise ValueError when its state is invalid."""
        if len(self.vertices) < 3 or not self.triangles:
            raise HumanoidMeshError("humanoid mesh is empty")

        for vertex in self.vertices:
            try:
                valid_vertex = len(vertex) == 3 and all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    for value in vertex
                )
            except (TypeError, OverflowError):
                valid_vertex = False
            if not valid_vertex:
                raise HumanoidMeshError("humanoid mesh contains invalid vertex coordinates")

        count = len(self.vertices)
        for tri in self.triangles:
            try:
                valid_triangle = len(tri) == 3 and all(
                    type(index) is int and 0 <= index < count for index in tri
                )
            except TypeError:
                valid_triangle = False
            if not valid_triangle:
                raise HumanoidMeshError("humanoid mesh contains an invalid face")
        return self


def _default_cache_path() -> Path:
    configured = os.environ.get(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser() / DEFAULT_CACHE_NAME
    return Path.home() / ".cache" / "freecad-cloth" / DEFAULT_CACHE_NAME


def _weights_cache_path() -> Path:
    configured = os.environ.get(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser() / DEFAULT_WEIGHTS_NAME
    return Path.home() / ".cache" / "freecad-cloth" / DEFAULT_WEIGHTS_NAME


def _skeleton_cache_path() -> Path:
    configured = os.environ.get(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser() / DEFAULT_SKELETON_NAME
    return Path.home() / ".cache" / "freecad-cloth" / DEFAULT_SKELETON_NAME


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
        if not isinstance(payload, dict):
            return False
        weights = payload.get("weights")
        if not isinstance(weights, dict) or not weights:
            return False

        has_entries = False
        for bone_name, entries in weights.items():
            if not isinstance(bone_name, str) or not isinstance(entries, list):
                return False
            for entry in entries:
                if not isinstance(entry, list) or len(entry) != 2:
                    return False
                index, weight = entry
                if type(index) is not int or index < 0:
                    return False
                if (
                    isinstance(weight, bool)
                    or not isinstance(weight, (int, float))
                    or not math.isfinite(weight)
                    or weight < 0.0
                ):
                    return False
                has_entries = True
        return has_entries
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError):
        return False


def _valid_skeleton_payload(payload: object) -> bool:
    """Return whether a decoded skeleton has usable bone and joint references."""
    if not isinstance(payload, dict):
        return False
    bones = payload.get("bones")
    joints = payload.get("joints")
    if not isinstance(bones, dict) or not bones or not isinstance(joints, dict) or not joints:
        return False
    for joint_name, indices in joints.items():
        if (
            not isinstance(joint_name, str)
            or not isinstance(indices, list)
            or any(type(index) is not int or index < 0 for index in indices)
        ):
            return False
    for bone_name, bone in bones.items():
        if not isinstance(bone_name, str) or not isinstance(bone, dict):
            return False
        head = bone.get("head")
        tail = bone.get("tail")
        if (
            not isinstance(head, str)
            or not isinstance(tail, str)
            or head not in joints
            or tail not in joints
            or not joints[head]
            or not joints[tail]
        ):
            return False
    return True


def _verified_skeleton(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != MAKEHUMAN_SKELETON_SIZE:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
        return _valid_skeleton_payload(payload)
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError):
        return False


def _download(url: str, destination: Path, verifier: Callable[[Path], bool]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".makehuman-", suffix=destination.suffix, dir=str(destination.parent)
    )
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
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def ensure_makehuman_base(path: str | os.PathLike[str] | None = None) -> Path:
    """Return a real human OBJ, using an explicit local override when supplied."""
    override = os.environ.get(CACHE_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError(f"explicit humanoid mesh path does not exist: {destination}")
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError(f"{CACHE_ENV} points to a missing humanoid mesh: {destination}")
        return destination

    destination = _default_cache_path()
    if _verified(destination):
        return destination
    try:
        _download(MAKEHUMAN_BASE_URL, destination, _verified)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman HM08 base mesh; "
            f"set {CACHE_ENV} to a local OBJ file or allow network access ({exc})"
        ) from exc
    return destination


def ensure_makehuman_weights(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned MakeHuman default skinning weights."""
    override = os.environ.get(WEIGHTS_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError(
                f"explicit MakeHuman weights path does not exist: {destination}"
            )
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError(
                f"{WEIGHTS_ENV} points to missing MakeHuman weights: {destination}"
            )
        return destination

    destination = _weights_cache_path()
    if _verified_weights(destination):
        return destination
    try:
        _download(MAKEHUMAN_WEIGHTS_URL, destination, _verified_weights)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman default weights; "
            f"set {WEIGHTS_ENV} to a local MHW file or allow network access ({exc})"
        ) from exc
    return destination


def ensure_makehuman_skeleton(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned MakeHuman default authored skeleton."""
    override = os.environ.get(SKELETON_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError(
                f"explicit MakeHuman skeleton path does not exist: {destination}"
            )
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            raise HumanoidMeshError(
                f"{SKELETON_ENV} points to missing MakeHuman skeleton: {destination}"
            )
        return destination

    destination = _skeleton_cache_path()
    if _verified_skeleton(destination):
        return destination
    try:
        _download(MAKEHUMAN_SKELETON_URL, destination, _verified_skeleton)
    except Exception as exc:
        raise HumanoidMeshError(
            "unable to obtain the pinned MakeHuman default skeleton; "
            f"set {SKELETON_ENV} to a local MHSkel file or allow network access ({exc})"
        ) from exc
    return destination


def _load_source_vertices(path: str | None = None) -> tuple[Point, ...]:
    source = ensure_makehuman_base(path)
    try:
        vertices: list[Point] = []
        for raw in source.read_text(encoding="utf-8", errors="strict").splitlines():
            fields = raw.split()
            if fields and fields[0] == "v" and len(fields) >= 4:
                point = (float(fields[1]), float(fields[2]), float(fields[3]))
                if not all(math.isfinite(value) for value in point):
                    raise ValueError("source vertex coordinates must be finite")
                vertices.append(point)
        if len(vertices) < 3:
            raise ValueError("source mesh contains fewer than three vertices")
        return tuple(vertices)
    except (OSError, UnicodeError, ValueError) as exc:
        raise HumanoidMeshError(
            f"unable to parse MakeHuman source vertices {source}: {exc}"
        ) from exc


@lru_cache(maxsize=4)
def load_makehuman_skeleton(path: str | None = None) -> SkeletonData:
    """Load and return the requested makehuman skeleton resource."""
    source = ensure_makehuman_skeleton(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise HumanoidMeshError(f"unable to parse MakeHuman skeleton {source}: {exc}") from exc
    if not _valid_skeleton_payload(payload):
        raise HumanoidMeshError(f"MakeHuman skeleton has invalid bones or joints: {source}")
    return cast(SkeletonData, payload)


def _joint_point(
    source_vertices: Sequence[Point],
    indices: Iterable[int],
    mapper: Callable[[Point], Point] | None = None,
) -> Point:
    """Average authored joint vertices, optionally after fitting each vertex.

    Fitting the average source point is not equivalent to averaging the fitted
    points when the mapping is nonlinear. The latter keeps rest-joint
    locations aligned with the actual fitted surface.
    """
    points = [
        source_vertices[int(index)] for index in indices if 0 <= int(index) < len(source_vertices)
    ]
    if not points:
        raise HumanoidMeshError("MakeHuman skeleton references missing joint vertices")
    fitted = [mapper(point) for point in points] if mapper is not None else points
    count = float(len(fitted))
    return (
        sum(point[0] for point in fitted) / count,
        sum(point[1] for point in fitted) / count,
        sum(point[2] for point in fitted) / count,
    )


def _bone_source_endpoints(
    source_vertices: Sequence[Point],
    skeleton: SkeletonData,
    bone_name: str,
    mapper: Callable[[Point], Point] | None = None,
) -> tuple[Point, Point]:
    """Return authored endpoints, optionally fitted vertex-by-vertex."""
    bone = skeleton["bones"].get(bone_name)
    if not bone:
        raise HumanoidMeshError(f"MakeHuman skeleton has no bone {bone_name}")
    return (
        _joint_point(source_vertices, skeleton["joints"][bone["head"]], mapper=mapper),
        _joint_point(source_vertices, skeleton["joints"][bone["tail"]], mapper=mapper),
    )


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
        tri for tri in triangles if all(0 <= index < MAKEHUMAN_BODY_VERTEX_COUNT for index in tri)
    )
    return MeshData(body_vertices, body_triangles).validate()


@lru_cache(maxsize=4)
def load_makehuman_mesh(path: str | None = None) -> MeshData:
    """Load and return the requested makehuman mesh resource."""
    source = ensure_makehuman_base(path)
    try:
        return parse_obj(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, HumanoidMeshError) as exc:
        raise HumanoidMeshError(f"unable to parse MakeHuman base mesh {source}: {exc}") from exc


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _smoothstep(a: float, b: float, x: float) -> float:
    if a == b:
        return 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _axis_bounds(vertices: Sequence[Point], axis: int) -> tuple[float, float]:
    values = [v[axis] for v in vertices]
    return min(values), max(values)


def _map_makehuman_axes(vertices: Sequence[Point]) -> list[Point]:
    """Convert MakeHuman's Y-up coordinates to FreeCAD RH-Z-up coordinates."""
    ymin, ymax = _axis_bounds(vertices, 1)
    span = max(1e-9, ymax - ymin)
    return [(float(x), float(z), float(y - ymin) / span) for x, y, z in vertices]


def _reoriented_triangles(triangles: Sequence[Triangle]) -> tuple[Triangle, ...]:
    """Reverse winding after the handedness-flipping Y/Z axis permutation."""
    return tuple((int(a), int(c), int(b)) for a, b, c in triangles)


def _profile_scale(z: float, profile: Sequence[tuple[float, float]]) -> float:
    for i in range(len(profile) - 1):
        z0, s0 = profile[i]
        z1, s1 = profile[i + 1]
        if z <= z1:
            return _lerp(s0, s1, _smoothstep(z0, z1, z))
    return profile[-1][1]


def _is_default_measurement_shape(parameters: AvatarParameters) -> bool:
    """Return whether the authoritative dimensions are the canonical defaults."""
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    return all(
        math.isclose(parameters.measurement(name), value, rel_tol=0.0, abs_tol=1e-9)
        for name, value in DEFAULT_MEASUREMENTS.items()
    )


def _measurement_profile(parameters: AvatarParameters) -> list[tuple[float, float]]:
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
    profile.extend(((0.75, 1.0), (1.0, 1.0)))
    return profile


def _measurement_axis_profiles(
    parameters: AvatarParameters,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Split circumference changes into anatomically asymmetric width/depth scales.

    A torso circumference is not a sphere radius. Hips and waists generally
    need a stronger lateral response, while depth still changes smoothly to
    preserve a plausible cross-section. Exponents sum to two so the average
    first-order cross-section scale remains close to the requested ratio.
    """
    bands = (
        ("hip", 0.50, 1.25),
        ("high_hip", 0.54, 1.20),
        ("waist", 0.58, 1.30),
        ("underbust", 0.64, 1.15),
        ("chest", 0.69, 1.15),
    )
    # Reuse the canonical per-measurement ratios so clamping and band placement
    # stay identical for both the legacy profile and its anisotropic version.
    ratios = _measurement_profile(parameters)
    lateral = [(0.42, 1.0)]
    depth = [(0.42, 1.0)]
    for index, (_name, height, lateral_exponent) in enumerate(bands, start=1):
        ratio = ratios[index][1]
        lateral.append((height, ratio**lateral_exponent))
        depth.append((height, ratio ** (2.0 - lateral_exponent)))
    lateral.extend(((0.75, 1.0), (1.0, 1.0)))
    depth.extend(((0.75, 1.0), (1.0, 1.0)))
    return lateral, depth


def _gender_axis_profiles(
    parameters: AvatarParameters,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Return separate lateral and depth shape fields for the body-shape blend."""
    delta = max(-0.5, min(0.5, float(parameters.gender) - 0.5))
    lateral = [
        (0.0, 1.0),
        (0.42, 1.0),
        (0.50, 1.0 - 0.16 * delta),
        (0.58, 1.0 + 0.10 * delta),
        (0.69, 1.0 + 0.04 * delta),
        (0.77, 1.0 + 0.14 * delta),
        (1.0, 1.0),
    ]
    # Depth changes are smaller than lateral changes; this avoids uniform
    # three-dimensional inflation while retaining the existing slider intent.
    depth = [
        (0.0, 1.0),
        (0.42, 1.0),
        (0.50, 1.0 - 0.04 * delta),
        (0.58, 1.0 + 0.03 * delta),
        (0.64, 1.0 + 0.04 * delta),
        (0.69, 1.0 + 0.06 * delta),
        (0.77, 1.0 + 0.02 * delta),
        (1.0, 1.0),
    ]
    return lateral, depth


def _estimate_shoulder_pivots(
    vertices: Sequence[Point], shoulder_half: float, shoulder_z: float, height_mm: float
) -> dict[float, float]:
    """Infer the shoulder rotation pivots from the fitted body surface."""
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


def _estimate_rest_arm_angles(
    vertices: Sequence[Point],
    shoulder_pivots: dict[float, float],
    shoulder_z: float,
    height_mm: float,
    arm_weights: tuple[Sequence[float], Sequence[float]] | None = None,
) -> dict[float, float]:
    """Estimate each HM08 arm's unposed angle from its actual A-pose geometry."""
    result = {}
    for side_index, side in enumerate((-1.0, 1.0)):
        pivot_x = shoulder_pivots.get(side, side * 0.0)
        weights = None if arm_weights is None else arm_weights[side_index]
        samples = []
        for index, (x, _y, z) in enumerate(vertices):
            if side * x <= side * pivot_x * 1.05:
                continue
            if not 0.50 <= z / max(1.0, height_mm) <= 0.78:
                continue
            influence = 1.0 if weights is None else weights[index]
            if influence <= 0.05:
                continue
            samples.append((x, z, influence))
        if not samples:
            result[side] = 0.0
            continue
        weighted_x = 0.0
        weighted_z = 0.0
        total = 0.0
        for x, z, influence in samples:
            weight = influence * max(0.1, side * (x - pivot_x))
            weighted_x += x * weight
            weighted_z += z * weight
            total += weight
        center_x = weighted_x / total
        center_z = weighted_z / total
        radial_x = max(1e-6, side * (center_x - pivot_x))
        downward = max(0.0, shoulder_z - center_z)
        result[side] = math.degrees(math.atan2(downward, radial_x))
    return result


def _is_arm_bone(name: str, side: str) -> bool:
    if not name.endswith(side):
        return False
    base = name[:-2]
    return base.startswith(("upperarm", "lowerarm", "wrist", "hand", "finger", "thumb"))


@lru_cache(maxsize=4)
def load_makehuman_arm_weights(
    vertex_count: int, path: str | None = None
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Load the source mesh's arm-chain weights, mapped onto visible vertices.

    These are authored by MakeHuman rather than inferred from lateral distance
    and height. Distal arms and fingers therefore retain full arm influence,
    while the shoulder transition follows the source skinning field.
    """
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
        raise HumanoidMeshError(f"unable to parse MakeHuman arm weights {source}: {exc}") from exc


def load_makehuman_weights(
    vertex_count: int, path: str | None = None
) -> dict[str, tuple[tuple[int, float], ...]]:
    """Load the complete MakeHuman skinning field for visible body vertices."""
    source = ensure_makehuman_weights(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
        raw = payload["weights"]
        result = {}
        for bone_name, entries in raw.items():
            filtered = []
            for index, weight in entries:
                index = int(index)
                if 0 <= index < vertex_count:
                    value = max(0.0, float(weight))
                    if value > 0.0:
                        filtered.append((index, value))
            if filtered:
                result[str(bone_name)] = tuple(filtered)
        if not result:
            raise HumanoidMeshError("MakeHuman weights contain no visible vertices")
        return result
    except (KeyError, OSError, UnicodeError, ValueError, TypeError) as exc:
        raise HumanoidMeshError(
            f"unable to parse MakeHuman skinning weights {source}: {exc}"
        ) from exc


def _make_source_fitted_mapper(
    source_vertices: Sequence[Point], parameters: AvatarParameters, skin_offset: float
) -> Callable[[Point], Point]:
    """Map source vertices using fixed calibration and localized dimensions.

    Axis calibration is pinned to the canonical body envelope. Measurement
    changes act only within their height bands so local edits cannot rescale
    unrelated regions such as the head. Skeleton callers use zero skin offset;
    padding is reserved for the visible surface.
    """
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    body = tuple(source_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT])
    ymin, ymax = _axis_bounds(body, 1)
    y_span = max(1e-9, ymax - ymin)
    x_min, x_max = _axis_bounds(body, 0)
    depth_min, depth_max = _axis_bounds(body, 2)
    source_width = max(1e-9, x_max - x_min)
    source_depth = max(1e-9, depth_max - depth_min)

    # Keep axis calibration independent of the edited torso profile. Otherwise
    # a hip/chest edit changes the global bounds and scales the entire mannequin.
    default_width = float(DEFAULT_MEASUREMENTS["shoulder"]) + 1.5 * float(
        DEFAULT_MEASUREMENTS["upper_arm"]
    )
    default_depth = float(DEFAULT_MEASUREMENTS["chest"]) / math.pi
    scale_x = default_width / source_width
    scale_y = default_depth / source_depth

    height_mm = float(parameters.measurement("height"))
    measurement_profile_x, measurement_profile_y = _measurement_axis_profiles(parameters)
    gender_profile_x, gender_profile_y = _gender_axis_profiles(parameters)
    if _is_default_measurement_shape(parameters):
        shoulder_scale = 1.0
    else:
        shoulder_scale = max(
            0.80,
            min(
                1.25,
                parameters.measurement("shoulder") / float(DEFAULT_MEASUREMENTS["shoulder"]),
            ),
        )

    core_width_profile = [
        (0.42, float(DEFAULT_MEASUREMENTS["hip"]) * 1.10 / (2.0 * math.pi)),
        (0.50, float(DEFAULT_MEASUREMENTS["hip"]) * 1.10 / (2.0 * math.pi)),
        (0.54, float(DEFAULT_MEASUREMENTS["high_hip"]) * 1.10 / (2.0 * math.pi)),
        (0.58, float(DEFAULT_MEASUREMENTS["waist"]) * 1.10 / (2.0 * math.pi)),
        (0.64, float(DEFAULT_MEASUREMENTS["underbust"]) * 1.10 / (2.0 * math.pi)),
        (0.69, float(DEFAULT_MEASUREMENTS["chest"]) * 1.10 / (2.0 * math.pi)),
        (0.75, float(DEFAULT_MEASUREMENTS["chest"]) * 1.10 / (2.0 * math.pi)),
        (0.83, float(DEFAULT_MEASUREMENTS["chest"]) * 0.80 / (2.0 * math.pi)),
        (1.00, float(DEFAULT_MEASUREMENTS["chest"]) * 0.80 / (2.0 * math.pi)),
    ]
    # Keep this mask fixed to the canonical shoulder location. Changing the
    # shoulder measurement must not make the influence envelope swallow hands.
    shoulder_half = float(DEFAULT_MEASUREMENTS["shoulder"]) / 2.0

    def transform(point: Point) -> Point:
        x, y, z = point
        normalized_z = (y - ymin) / y_span

        # Start from stable source coordinates. Region masks are evaluated in
        # this calibrated frame so a waist/chest edit cannot stretch a hand
        # merely because the posed hand happens to share that height band.
        base_x_mm = x * scale_x
        base_y_mm = z * scale_y
        torso_measurement_x = _profile_scale(normalized_z, measurement_profile_x)
        torso_measurement_y = _profile_scale(normalized_z, measurement_profile_y)
        gender_scale_x = _profile_scale(normalized_z, gender_profile_x)
        gender_scale_y = _profile_scale(normalized_z, gender_profile_y)

        # Estimate a stable trunk envelope from canonical measurements. Its
        # dimensions deliberately do not depend on the edited measurements,
        # preventing the influence mask from expanding into the arms as the
        # user changes chest or waist values.
        core_half_width = _profile_scale(normalized_z, core_width_profile)
        core_influence = 1.0 - _smoothstep(core_half_width, core_half_width + 45.0, abs(base_x_mm))
        torso_height_influence = _smoothstep(0.36, 0.43, normalized_z) * (
            1.0 - _smoothstep(0.75, 0.83, normalized_z)
        )
        torso_influence = max(0.0, min(1.0, core_influence * torso_height_influence))
        torso_measurement_x = _lerp(1.0, torso_measurement_x, torso_influence)
        torso_measurement_y = _lerp(1.0, torso_measurement_y, torso_influence)

        # Body-blend width changes also reach the shoulder girdle, but taper
        # away along the upper arms. Circumference controls remain restricted
        # to the trunk. This keeps broad shoulders anatomically distinct from
        # a uniformly inflated chest cross-section.
        shoulder_rise = _smoothstep(0.67, 0.75, normalized_z)
        shoulder_fall = 1.0 - _smoothstep(0.80, 0.88, normalized_z)
        shoulder_blend = shoulder_rise * shoulder_fall
        shoulder_envelope = 1.0 - _smoothstep(
            shoulder_half + 10.0, shoulder_half + 75.0, abs(base_x_mm)
        )
        shoulder_influence = shoulder_blend * shoulder_envelope
        body_blend_influence = max(torso_influence, shoulder_influence)
        gender_scale_x = _lerp(1.0, gender_scale_x, body_blend_influence)
        gender_scale_y = _lerp(1.0, gender_scale_y, torso_influence)
        lateral_scale = _lerp(1.0, shoulder_scale, shoulder_influence)

        x_mm = base_x_mm * torso_measurement_x * gender_scale_x * lateral_scale
        y_mm = base_y_mm * torso_measurement_y * gender_scale_y
        radius = math.hypot(x_mm, y_mm)
        if radius > 1e-9 and skin_offset:
            x_mm += x_mm / radius * skin_offset
            y_mm += y_mm / radius * skin_offset
        z_mm = normalized_z * height_mm

        # Keep the authored breast control local to the chest. Its broader,
        # flatter influence gives a less spherical silhouette than a narrow
        # isotropic bump and does not affect unrelated limb vertices.
        breast_size = min(
            1.0,
            float(parameters.breast_size) + max(0.0, 0.5 - float(parameters.gender)) * 1.2,
        )
        if breast_size > 0.0 and 0.60 <= normalized_z <= 0.76 and abs(base_x_mm) < 190.0:
            front_weight = _smoothstep(-18.0, 28.0, y_mm)
            vertical_weight = math.exp(-0.5 * ((normalized_z - 0.685) / 0.030) ** 2)
            lateral_weight = max(
                math.exp(-0.5 * ((x_mm - center_x) / 58.0) ** 2) for center_x in (-72.0, 72.0)
            )
            y_mm += 62.0 * breast_size * front_weight * vertical_weight * lateral_weight
        return (x_mm, y_mm, z_mm)

    return transform


def _authored_arm_rig_points(parameters: AvatarParameters) -> dict[float, dict[str, Point]]:
    source = _load_source_vertices()
    skeleton = load_makehuman_skeleton()
    transform = _make_source_fitted_mapper(source, parameters, 0.0)
    points = {}
    for physical_side, suffix in ((-1.0, ".L"), (1.0, ".R")):
        shoulder = _bone_source_endpoints(source, skeleton, "upperarm01" + suffix, mapper=transform)[0]
        wrist = _bone_source_endpoints(source, skeleton, "wrist" + suffix, mapper=transform)[0]
        points[physical_side] = {"shoulder": shoulder, "wrist": wrist}

    if points[-1.0]["shoulder"][0] > points[1.0]["shoulder"][0]:
        points[-1.0], points[1.0] = points[1.0], points[-1.0]
    return points


def fit_makehuman_mesh(
    mesh: MeshData,
    parameters: AvatarParameters,
    arm_weights: tuple[Sequence[float], Sequence[float]] | None = None,
) -> MeshData:
    """Fit HM08 and pose arms using source-authored bones and skinning weights."""
    mesh.validate()
    height_mm = float(parameters.measurement("height"))
    transform = _make_source_fitted_mapper(mesh.vertices, parameters, float(parameters.skin_offset))
    fitted = tuple(transform(point) for point in mesh.vertices)

    pose = parameters.pose
    shoulder_half = float(parameters.measurement("shoulder")) / 2.0
    shoulder_z = height_mm * 0.76
    shoulder_pivots = _estimate_shoulder_pivots(fitted, shoulder_half, shoulder_z, height_mm)
    if arm_weights is not None:
        try:
            authored = _authored_arm_rig_points(parameters)
            shoulder_pivots = {side: authored[side]["shoulder"][0] for side in (-1.0, 1.0)}
            rest_angles = {}
            for side in (-1.0, 1.0):
                shoulder = authored[side]["shoulder"]
                wrist = authored[side]["wrist"]
                radial = max(1e-9, side * (wrist[0] - shoulder[0]))
                downward = max(0.0, shoulder[2] - wrist[2])
                rest_angles[side] = math.degrees(math.atan2(downward, radial))
        except (HumanoidMeshError, KeyError, OSError, UnicodeError, ValueError, TypeError):
            rest_angles = _estimate_rest_arm_angles(
                fitted, shoulder_pivots, shoulder_z, height_mm, arm_weights
            )
    else:
        rest_angles = _estimate_rest_arm_angles(
            fitted, shoulder_pivots, shoulder_z, height_mm, arm_weights
        )

    default_angle = {
        "t_pose": 12.0,
        "standing": 12.0,
        "sewing": 55.0,
        "sitting": 25.0,
    }.get(pose.preset, 12.0)
    left_angle = (
        default_angle
        if pose.preset != "standing" and float(pose.left_arm_angle) == 12.0
        else float(pose.left_arm_angle)
    )
    right_angle = (
        default_angle
        if pose.preset != "standing" and float(pose.right_arm_angle) == 12.0
        else float(pose.right_arm_angle)
    )
    posed = []
    for index, (x, y, z) in enumerate(fitted):
        side = -1.0 if x < 0.0 else 1.0
        pivot_x = shoulder_pivots.get(side, side * shoulder_half)
        source_weight = None if arm_weights is None else arm_weights[0 if side < 0 else 1][index]
        weight = _arm_pose_weight(x, z, pivot_x, height_mm, source_weight)
        if weight <= 1e-9:
            posed.append((x, y, z))
            continue
        desired = left_angle if side < 0 else right_angle
        delta = desired - rest_angles.get(side, 0.0)
        if abs(delta) <= 1e-9:
            posed.append((x, y, z))
            continue
        radians = side * math.radians(delta)
        dx = x - pivot_x
        dz = z - shoulder_z
        cosine = math.cos(radians)
        sine = math.sin(radians)
        rotated_x = pivot_x + cosine * dx + sine * dz
        rotated_z = shoulder_z - sine * dx + cosine * dz
        x = x + weight * (rotated_x - x)
        z = z + weight * (rotated_z - z)
        posed.append((x, y, z))
    return MeshData(tuple(posed), _reoriented_triangles(mesh.triangles)).validate()


def _arm_pose_weight(
    x: float,
    z: float,
    shoulder_pivot_x: float,
    height_mm: float,
    source_weight: float | None = None,
) -> float:
    """Return source-authored arm influence, with a geometric legacy fallback."""
    if source_weight is not None:
        return max(0.0, min(1.0, float(source_weight)))
    pivot = abs(shoulder_pivot_x)
    lateral = _smoothstep(pivot * 0.98, pivot * 1.12, abs(x))
    nz = z / max(1.0, height_mm)
    # The articulated hand/wrist can hang well below chest height; keep the
    # geometric fallback active through the lower arm envelope while preserving
    # the upper torso cutoff.
    vertical = _smoothstep(0.28, 0.34, nz) * (1.0 - _smoothstep(0.88, 0.96, nz))
    return lateral * vertical


def build_humanoid_mesh(
    parameters: AvatarParameters, source_path: str | os.PathLike[str] | None = None
) -> MeshData:
    """Load, fit and return the real MakeHuman mannequin mesh for Cloth."""
    source = load_makehuman_mesh(str(source_path) if source_path is not None else None)
    arm_weights = (
        None if source_path is not None else load_makehuman_arm_weights(len(source.vertices))
    )
    return fit_makehuman_mesh(source, parameters, arm_weights=arm_weights)

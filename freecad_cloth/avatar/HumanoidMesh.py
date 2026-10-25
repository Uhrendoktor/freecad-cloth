# Copyright (C) 2026 FreeCAD Cloth contributors
"""MakeHuman-backed humanoid mesh provider.

The avatar is a real polygonal human base mesh rather than a collection of
FreeCAD primitives. The pinned MakeHuman HM08 base mesh is reused from a
matching local installation when available, otherwise fetched lazily and cached
locally before fitting into the Cloth millimetre coordinate system.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Self, cast
from urllib.request import Request, urlopen

from pydantic import StrictInt

import numpy as np
import trimesh
from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.avatar.MakeHumanTargets import (
    apply_measurement_targets,
    resolve_target,
    target_directory,
)
from freecad_cloth.avatar.SkeletonTypes import BoneData, SkeletonData
from freecad_cloth.common.MeshTopology import triangle_indices_are_valid

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
_SHOULDER_START_HEIGHT_RATIO = 0.68
_SHOULDER_END_HEIGHT_RATIO = 0.82
_ARM_START_HEIGHT_RATIO = 0.50
_ARM_END_HEIGHT_RATIO = 0.78
_ARM_PIVOT_SEPARATION_FACTOR = 1.05
_ARM_MIN_INFLUENCE = 0.05
_ARM_MIN_LEVER_ARM_MM = 0.1
_ARM_MIN_RADIAL_DISTANCE_MM = 1e-6
CACHE_ENV = "FREECAD_CLOTH_AVATAR_MESH"
MAKEHUMAN_DATA_ENV = "FREECAD_CLOTH_MAKEHUMAN_DATA"
CACHE_DIR_ENV = "FREECAD_CLOTH_AVATAR_CACHE"
WEIGHTS_ENV = "FREECAD_CLOTH_AVATAR_WEIGHTS"
SKELETON_ENV = "FREECAD_CLOTH_AVATAR_SKELETON"
DEFAULT_CACHE_NAME = "makehuman-hm08-base.obj"
DEFAULT_WEIGHTS_NAME = "makehuman-default-weights.mhw"
DEFAULT_SKELETON_NAME = "makehuman-default.mhskel"

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from freecad_cloth.avatar.AvatarModel import AvatarParameters

Point = tuple[float, float, float]
Triangle = tuple[int, int, int]


class HumanoidMeshError(RuntimeError):
    """Raised when the real humanoid mesh cannot be loaded or fitted."""


@pydantic_dataclass(frozen=True)
class MeshData:
    """Public data model or service class for MeshData."""

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[StrictInt, StrictInt, StrictInt], ...]

    def validate(self) -> Self:
        """Validate this mesh's finite coordinates and triangle indices.

        Returns:
            The same mesh after validation.

        Raises:
            HumanoidMeshError: If the mesh is empty, has invalid coordinates, or
                contains a face with an invalid vertex index.
        """
        if len(self.vertices) < 3 or not self.triangles:
            msg = "humanoid mesh is empty"
            raise HumanoidMeshError(msg)

        vertices: np.ndarray | None = None
        valid_vertices = False
        try:
            vertices = np.asarray(self.vertices, dtype=np.float64)
            valid_vertices = vertices.shape == (len(self.vertices), 3) and bool(
                np.isfinite(vertices).all()
            )
        except (TypeError, ValueError, OverflowError):
            valid_vertices = False
        if vertices is None or not valid_vertices:
            msg = "humanoid mesh contains invalid vertex coordinates"
            raise HumanoidMeshError(msg)

        valid_triangles = triangle_indices_are_valid(self.triangles, len(vertices))
        if not valid_triangles:
            msg = "humanoid mesh contains an invalid face"
            raise HumanoidMeshError(msg)
        return self


def _default_cache_path(environ: Mapping[str, str] | None = None) -> Path:
    settings = os.environ if environ is None else environ
    configured = settings.get(CACHE_DIR_ENV, "").strip()
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
            msg = "downloaded MakeHuman asset failed verification"
            raise HumanoidMeshError(msg)
        Path(temporary).replace(destination)
    except Exception:
        with contextlib.suppress(OSError):
            Path(temporary).unlink()
        raise


def _makehuman_base_mesh_candidates(environ: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    """Return conventional MakeHuman install paths without scanning the whole disk."""
    settings = os.environ if environ is None else environ
    roots: list[Path] = []
    candidates: list[Path] = []
    configured = settings.get(MAKEHUMAN_DATA_ENV, "").strip()
    if configured:
        explicit = Path(configured).expanduser()
        if explicit.suffix.lower() == ".obj":
            candidates.append(explicit)
        roots.append(explicit)

    home = Path.home()
    roots.extend(
        (
            home / ".local" / "share" / "makehuman",
            home / ".config" / "makehuman",
            home / ".var" / "app" / "org.makehuman.MakeHuman" / "data",
            home / "makehuman",
            home / "MakeHuman",
            home / "makehuman-community",
            home / "src" / "makehuman",
            home / "Development" / "makehuman",
            Path("/usr/share/makehuman"),
            Path("/usr/local/share/makehuman"),
            Path("/usr/share"),
            Path("/usr/local/share"),
            Path("/opt/makehuman"),
            Path("/opt/MakeHuman"),
            Path("/opt/makehuman-community"),
            Path("/Applications/MakeHuman.app"),
            home / "Applications" / "MakeHuman.app",
        )
    )
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        value = settings.get(variable, "").strip()
        if value:
            install_root = Path(value).expanduser()
            roots.extend(
                (
                    install_root / "MakeHuman",
                    install_root / "MakeHumanCommunity",
                    install_root / "makehuman",
                )
            )
    for variable in ("LOCALAPPDATA", "APPDATA"):
        value = settings.get(variable, "").strip()
        if value:
            profile_root = Path(value).expanduser()
            roots.extend(
                (
                    profile_root / "Programs" / "MakeHuman",
                    profile_root / "MakeHuman",
                    profile_root / "makehuman",
                )
            )

    layouts = (
        Path("3dobjs") / "base.obj",
        Path("data") / "3dobjs" / "base.obj",
        Path("makehuman") / "data" / "3dobjs" / "base.obj",
        Path("makehuman") / "makehuman" / "data" / "3dobjs" / "base.obj",
        Path("Contents") / "Resources" / "makehuman" / "data" / "3dobjs" / "base.obj",
        Path("Contents") / "Resources" / "data" / "3dobjs" / "base.obj",
        Path("Resources") / "makehuman" / "data" / "3dobjs" / "base.obj",
    )
    for root in roots:
        candidates.extend(root / layout for layout in layouts)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return tuple(unique)


def _find_local_base_mesh(
    *,
    environ: Mapping[str, str] | None = None,
    verifier: Callable[[Path], bool] | None = None,
) -> Path | None:
    """Find a local copy only if its bytes match the pinned indexed HM08 mesh."""
    check = _verified if verifier is None else verifier
    for candidate in _makehuman_base_mesh_candidates(environ):
        if check(candidate):
            return candidate
    return None


def ensure_makehuman_base(
    path: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    verifier: Callable[[Path], bool] | None = None,
    downloader: Callable[[str, Path, Callable[[Path], bool]], None] | None = None,
) -> Path:
    """Resolve a human OBJ from an explicit path, local install, or pinned download."""
    settings = os.environ if environ is None else environ
    check = _verified if verifier is None else verifier
    download = _download if downloader is None else downloader
    override = settings.get(CACHE_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            msg = f"explicit humanoid mesh path does not exist: {destination}"
            raise HumanoidMeshError(msg)
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            msg = f"{CACHE_ENV} points to a missing humanoid mesh: {destination}"
            raise HumanoidMeshError(msg)
        return destination

    destination = _default_cache_path(settings)
    if check(destination):
        return destination
    local_mesh = _find_local_base_mesh(environ=settings, verifier=check)
    if local_mesh is not None:
        return local_mesh
    try:
        download(MAKEHUMAN_BASE_URL, destination, check)
    except Exception as exc:
        msg = (
            "unable to obtain the pinned MakeHuman HM08 base mesh; set "
            f"{MAKEHUMAN_DATA_ENV} to a MakeHuman install/data directory, set "
            f"{CACHE_ENV} to a local OBJ file, or allow network access ({exc})"
        )
        raise HumanoidMeshError(msg) from exc
    return destination


def ensure_makehuman_weights(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned MakeHuman default skinning weights."""
    override = os.environ.get(WEIGHTS_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            msg = f"explicit MakeHuman weights path does not exist: {destination}"
            raise HumanoidMeshError(msg)
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            msg = f"{WEIGHTS_ENV} points to missing MakeHuman weights: {destination}"
            raise HumanoidMeshError(msg)
        return destination

    destination = _weights_cache_path()
    if _verified_weights(destination):
        return destination
    try:
        _download(MAKEHUMAN_WEIGHTS_URL, destination, _verified_weights)
    except Exception as exc:
        msg = (
            "unable to obtain the pinned MakeHuman default weights; "
            f"set {WEIGHTS_ENV} to a local MHW file or allow network access ({exc})"
        )
        raise HumanoidMeshError(msg) from exc
    return destination


def ensure_makehuman_skeleton(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the pinned MakeHuman default authored skeleton."""
    override = os.environ.get(SKELETON_ENV, "").strip()
    if path is not None:
        destination = Path(path).expanduser()
        if not destination.is_file():
            msg = f"explicit MakeHuman skeleton path does not exist: {destination}"
            raise HumanoidMeshError(msg)
        return destination
    if override:
        destination = Path(override).expanduser()
        if not destination.is_file():
            msg = f"{SKELETON_ENV} points to missing MakeHuman skeleton: {destination}"
            raise HumanoidMeshError(msg)
        return destination

    destination = _skeleton_cache_path()
    if _verified_skeleton(destination):
        return destination
    try:
        _download(MAKEHUMAN_SKELETON_URL, destination, _verified_skeleton)
    except Exception as exc:
        msg = (
            "unable to obtain the pinned MakeHuman default skeleton; "
            f"set {SKELETON_ENV} to a local MHSkel file or allow network access ({exc})"
        )
        raise HumanoidMeshError(msg) from exc
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
                    msg = "source vertex coordinates must be finite"
                    raise ValueError(msg)
                vertices.append(point)
        if len(vertices) < 3:
            msg = "source mesh contains fewer than three vertices"
            raise ValueError(msg)
        return tuple(vertices)
    except (OSError, UnicodeError, ValueError) as exc:
        msg = f"unable to parse MakeHuman source vertices {source}: {exc}"
        raise HumanoidMeshError(msg) from exc


@lru_cache(maxsize=4)
def load_makehuman_skeleton(path: str | None = None) -> SkeletonData:
    """Load and return the requested makehuman skeleton resource."""
    source = ensure_makehuman_skeleton(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError) as exc:
        msg = f"unable to parse MakeHuman skeleton {source}: {exc}"
        raise HumanoidMeshError(msg) from exc
    if not _valid_skeleton_payload(payload):
        msg = f"MakeHuman skeleton has invalid bones or joints: {source}"
        raise HumanoidMeshError(msg)
    return cast("SkeletonData", payload)


def _joint_point(
    source_vertices: Sequence[Point],
    indices: Iterable[int],
    mapper: Callable[[Point], Point] | None = None,
) -> Point:
    """Average authored joint vertices after optional per-vertex fitting.

    Fitting the average source point is not equivalent to averaging fitted
    points when the mapping is nonlinear; averaging mapped vertices keeps
    joint locations aligned with the actual fitted surface.

    Args:
        source_vertices: Authored MakeHuman vertex coordinates.
        indices: Indices defining the joint's contributing source vertices.
        mapper: Optional source-to-fitted-coordinate transform.

    Returns:
        The mean mapped joint coordinate.

    Raises:
        HumanoidMeshError: If no valid source vertices define the joint.
    """
    points = [
        source_vertices[int(index)] for index in indices if 0 <= int(index) < len(source_vertices)
    ]
    if not points:
        msg = "MakeHuman skeleton references missing joint vertices"
        raise HumanoidMeshError(msg)
    fitted = [mapper(point) for point in points] if mapper is not None else points
    mean = np.mean(np.asarray(fitted, dtype=np.float64), axis=0)
    return (float(mean[0]), float(mean[1]), float(mean[2]))


def _bone_source_endpoints(
    source_vertices: Sequence[Point],
    skeleton: SkeletonData,
    bone_name: str,
    mapper: Callable[[Point], Point] | None = None,
) -> tuple[Point, Point]:
    """Return authored endpoints, optionally fitted vertex-by-vertex."""
    bone = skeleton["bones"].get(bone_name)
    if not bone:
        msg = f"MakeHuman skeleton has no bone {bone_name}"
        raise HumanoidMeshError(msg)
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
            triangles.extend(
                (indices[0], indices[i], indices[i + 1]) for i in range(1, len(indices) - 1)
            )

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
        msg = f"unable to parse MakeHuman base mesh {source}: {exc}"
        raise HumanoidMeshError(msg) from exc


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _smoothstep(a: float, b: float, x: float) -> float:
    if a == b:
        return 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _map_makehuman_axes(vertices: Sequence[Point]) -> list[Point]:
    """Convert MakeHuman coordinates to FreeCAD's right-handed Z-up system.

    Args:
        vertices: Finite MakeHuman coordinates in the source Y-up system.

    Returns:
        Coordinates with the source Y axis mapped to vertical Z and normalized
        to a unit height, preserving X and mapping source Z to FreeCAD Y.
    """
    coordinates = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    heights = coordinates[:, 1]
    ymin = float(np.min(heights))
    ymax = float(np.max(heights))
    span = max(1e-9, ymax - ymin)
    mapped = np.column_stack((coordinates[:, 0], coordinates[:, 2], (heights - ymin) / span))
    return [(float(x), float(y), float(z)) for x, y, z in mapped]


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
    # Reuse canonical measurement ratios so clamping and band placement remain
    # identical between isotropic and anisotropic scaling.
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
    vertices: Sequence[Point], shoulder_half: float, height_mm: float
) -> dict[float, float]:
    """Infer shoulder pivots from the fitted body surface.

    Args:
        vertices: Fitted body mesh coordinates.
        shoulder_half: Expected half-width of the shoulder measurement.
        height_mm: Fitted mannequin height in millimetres.

    Returns:
        A mapping from side (-1 or +1) to the estimated shoulder X coordinate.
    """
    coordinates = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    x_coordinates = coordinates[:, 0]
    height_ratios = coordinates[:, 2] / max(1.0, height_mm)
    pivots = {}
    for side in (-1.0, 1.0):
        side_coordinates = side * x_coordinates
        selection = (
            (side_coordinates >= shoulder_half * 0.55)
            & (height_ratios >= _SHOULDER_START_HEIGHT_RATIO)
            & (height_ratios <= _SHOULDER_END_HEIGHT_RATIO)
        )
        lateral = np.sort(side_coordinates[selection])
        if not lateral.size:
            pivots[side] = side * shoulder_half
            continue
        count = max(1, int(np.ceil(lateral.size * 0.15)))
        medial = float(np.mean(lateral[:count], dtype=np.float64))
        medial = max(shoulder_half * 0.70, min(shoulder_half * 0.99, medial))
        pivots[side] = side * medial
    return pivots


def _estimate_side_rest_arm_angle(
    coordinates: np.ndarray,
    side: float,
    rig: tuple[float, float, float],
    influences: np.ndarray,
) -> float:
    """Estimate one side's downward arm angle from its weighted mesh envelope.

    Args:
        coordinates: Fitted three-dimensional mesh coordinates.
        side: Sign identifying the left (-1) or right (+1) arm.
        rig: Shoulder X coordinate, shoulder Z coordinate, and total height.
        influences: Per-vertex arm-chain weights.

    Returns:
        The estimated downward arm angle in degrees, or zero when no vertices
        qualify as part of the arm envelope.
    """
    pivot_x, shoulder_z, height_mm = rig
    height_ratios = coordinates[:, 2] / max(1.0, height_mm)
    selected = (
        (side * coordinates[:, 0] > side * pivot_x * _ARM_PIVOT_SEPARATION_FACTOR)
        & (height_ratios >= _ARM_START_HEIGHT_RATIO)
        & (height_ratios <= _ARM_END_HEIGHT_RATIO)
        & (influences > _ARM_MIN_INFLUENCE)
    )
    if not bool(np.any(selected)):
        return 0.0
    samples = coordinates[selected][:, (0, 2)]
    lever_arms = np.maximum(
        _ARM_MIN_LEVER_ARM_MM,
        side * (samples[:, 0] - pivot_x),
    )
    weight_factors = influences[selected] * lever_arms
    center = np.average(samples, axis=0, weights=weight_factors)
    radial_x = max(
        _ARM_MIN_RADIAL_DISTANCE_MM,
        side * (float(center[0]) - pivot_x),
    )
    downward = max(0.0, shoulder_z - float(center[1]))
    return math.degrees(math.atan2(downward, radial_x))


def _estimate_rest_arm_angles(
    vertices: Sequence[Point],
    shoulder_pivots: dict[float, float],
    shoulder_z: float,
    height_mm: float,
    arm_weights: tuple[Sequence[float], Sequence[float]] | None = None,
) -> dict[float, float]:
    """Estimate each HM08 arm's unposed angle from its actual A-pose geometry.

    Args:
        vertices: Fitted mesh vertex coordinates.
        shoulder_pivots: Estimated shoulder X coordinate for each side.
        shoulder_z: Shoulder height in millimetres.
        height_mm: Fitted mannequin height in millimetres.
        arm_weights: Optional per-vertex influence weights for the left and
            right arm chains.

    Returns:
        Unposed downward arm angles in degrees, keyed by side.

    Raises:
        HumanoidMeshError: If supplied arm weights do not match the vertex count.
    """
    coordinates = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    result = {}
    for side_index, side in enumerate((-1.0, 1.0)):
        pivot_x = shoulder_pivots.get(side, side * 0.0)
        influences = (
            np.ones(len(coordinates), dtype=np.float64)
            if arm_weights is None
            else np.asarray(arm_weights[side_index], dtype=np.float64)
        )
        if influences.shape != (len(coordinates),):
            msg = "MakeHuman arm weights must match the fitted vertex count"
            raise HumanoidMeshError(msg)
        result[side] = _estimate_side_rest_arm_angle(
            coordinates,
            side,
            (pivot_x, shoulder_z, height_mm),
            influences,
        )
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
        msg = f"unable to parse MakeHuman arm weights {source}: {exc}"
        raise HumanoidMeshError(msg) from exc


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
            msg = "MakeHuman weights contain no visible vertices"
            raise HumanoidMeshError(msg)
        return result
    except (KeyError, OSError, UnicodeError, ValueError, TypeError) as exc:
        msg = f"unable to parse MakeHuman skinning weights {source}: {exc}"
        raise HumanoidMeshError(msg) from exc


def _section_circumference(
    mesh: trimesh.Trimesh,
    plane: float,
    vertical_axis: int = 2,
    max_width: float | None = None,
) -> float:
    """Measure a closed mesh-section perimeter at a horizontal height plane.

    Trimesh performs triangle/plane intersections in vectorized code. The
    remaining graph pass connects the smaller set of section segments,
    selecting the largest centered closed loop so disconnected limb sections
    do not accidentally become the body circumference.

    Args:
        mesh: Triangulated fitted body mesh to intersect with the section plane.
        plane: Coordinate of the section plane on the chosen vertical axis.
        vertical_axis: Coordinate axis normal to the section plane.
        max_width: Optional maximum lateral span for an accepted loop.

    Returns:
        Perimeter of the largest centered closed contour, or zero when no valid
        closed contour meets the selection constraints.

    Raises:
        ValueError: If vertical_axis is not one of the three coordinate axes.
    """
    if vertical_axis not in (0, 1, 2):
        msg = "vertical_axis must be 0, 1, or 2"
        raise ValueError(msg)
    axes = tuple(axis for axis in range(3) if axis != vertical_axis)
    plane_normal = np.zeros(3, dtype=np.float64)
    plane_normal[vertical_axis] = 1.0
    plane_origin = np.zeros(3, dtype=np.float64)
    plane_origin[vertical_axis] = plane
    segments = trimesh.intersections.mesh_plane(
        mesh,
        plane_normal=plane_normal,
        plane_origin=plane_origin,
    )
    if not len(segments):
        return 0.0

    node_points: dict[tuple[int, int], tuple[float, float]] = {}
    graph: dict[tuple[int, int], set[tuple[int, int]]] = {}
    segment_seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    for segment in segments:
        first = (float(segment[0, axes[0]]), float(segment[0, axes[1]]))
        second = (float(segment[1, axes[0]]), float(segment[1, axes[1]]))
        first_key = (round(first[0] * 10000), round(first[1] * 10000))
        second_key = (round(second[0] * 10000), round(second[1] * 10000))
        if first_key == second_key:
            continue
        edge = (min(first_key, second_key), max(first_key, second_key))
        if edge in segment_seen:
            continue
        segment_seen.add(edge)
        node_points.setdefault(first_key, first)
        node_points.setdefault(second_key, second)
        graph.setdefault(first_key, set()).add(second_key)
        graph.setdefault(second_key, set()).add(first_key)

    if not graph:
        return 0.0

    loops: list[tuple[float, float, float, float]] = []
    visited: set[tuple[int, int]] = set()
    for seed in graph:
        if seed in visited:
            continue
        component: set[tuple[int, int]] = set()
        stack = [seed]
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(graph[current] - component)
        visited.update(component)
        if len(component) < 3 or any(len(graph[key]) != 2 for key in component):
            continue
        start = min(component)
        ordered = [start]
        previous: tuple[int, int] | None = None
        current = start
        closed = False
        for _ in range(len(component) + 1):
            options = sorted(key for key in graph[current] if key != previous)
            if not options:
                break
            following = options[0]
            if following == start:
                closed = True
                break
            if following in ordered:
                break
            ordered.append(following)
            previous, current = current, following
        if not closed or len(ordered) < 3:
            continue
        point_array = np.asarray([node_points[key] for key in ordered], dtype=np.float64)
        following_points = np.roll(point_array, -1, axis=0)
        edges = following_points - point_array
        perimeter = float(np.sum(np.linalg.norm(edges, axis=1), dtype=np.float64))
        twice_area = np.sum(
            point_array[:, 0] * following_points[:, 1] - following_points[:, 0] * point_array[:, 1],
            dtype=np.float64,
        )
        area = abs(float(twice_area)) * 0.5
        centroid_x = float(np.mean(point_array[:, 0], dtype=np.float64))
        width = float(np.ptp(point_array[:, 0]))
        if area > 1e-5 and perimeter > 1e-5:
            loops.append((area, perimeter, abs(centroid_x), width))

    central = [
        item for item in loops if item[2] <= 100.0 and (max_width is None or item[3] <= max_width)
    ]
    if not central:
        return 0.0
    # A body cross-section is the largest centered closed contour, not the
    # disconnected left/right arm or leg loops that can share its height.
    return max(central, key=lambda item: item[0])[1]


def _make_source_fitted_mapper(
    source_vertices: Sequence[Point],
    parameters: AvatarParameters,
    skin_offset: float,
    source_triangles: Sequence[Triangle] | None = None,
) -> Callable[[Point], Point]:
    """Map source vertices using fixed calibration and localized dimensions.

    Axis calibration is pinned to the canonical body envelope. Measurement
    changes act only within their height bands so local edits cannot rescale
    unrelated regions such as the head. Skeleton callers use zero skin offset;
    padding is reserved for the visible surface. When the source topology is
    supplied, a section-contour pass iteratively calibrates the named torso
    rings to their requested circumference in millimetres.

    Args:
        source_vertices: Source mesh vertices used to calibrate the fit.
        parameters: Authoritative mannequin measurements and pose settings.
        skin_offset: Outward offset in millimetres for the visible surface.
        source_triangles: Optional source topology for contour-based calibration.

    Returns:
        A callable mapping one source coordinate to its fitted 3D coordinate.
    """
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    body = tuple(source_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT])
    body_coordinates = np.asarray(body, dtype=np.float64).reshape((-1, 3))
    body_minimums = np.min(body_coordinates, axis=0)
    body_maximums = np.max(body_coordinates, axis=0)
    ymin, ymax = float(body_minimums[1]), float(body_maximums[1])
    y_span = max(1e-9, ymax - ymin)
    x_min, x_max = float(body_minimums[0]), float(body_maximums[0])
    depth_min, depth_max = float(body_minimums[2]), float(body_maximums[2])
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
    target_root = target_directory()
    use_gender_targets = bool(
        target_root
        and resolve_target("macrodetails/gender/female", target_root)
        and resolve_target("macrodetails/gender/male", target_root)
    )
    use_breast_target = bool(
        target_root and resolve_target("breast/breast-volume-vert-up", target_root)
    )
    if use_gender_targets:
        # Authored gender targets provide the broad anatomical silhouette;
        # don't stack the procedural gender scale on top of those deltas.
        gender_profile_x = [(height, 1.0) for height, _scale in gender_profile_x]
        gender_profile_y = [(height, 1.0) for height, _scale in gender_profile_y]
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
        """Map one source coordinate into the fitted mannequin frame.

        Args:
            point: Source-space XYZ coordinate using MakeHuman's Y-up convention.

        Returns:
            Fitted XYZ coordinate in millimetres using FreeCAD's Z-up convention.
        """
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
        fallback_breast_size = 0.0 if use_breast_target else float(parameters.breast_size)
        fallback_gender_fullness = (
            0.0 if use_gender_targets else max(0.0, 0.5 - float(parameters.gender)) * 1.2
        )
        breast_size = min(1.0, fallback_breast_size + fallback_gender_fullness)
        if breast_size > 0.0 and 0.60 <= normalized_z <= 0.76 and abs(base_x_mm) < 190.0:
            front_weight = _smoothstep(-18.0, 28.0, y_mm)
            vertical_weight = math.exp(-0.5 * ((normalized_z - 0.685) / 0.030) ** 2)
            lateral_weight = max(
                math.exp(-0.5 * ((x_mm - center_x) / 58.0) ** 2) for center_x in (-72.0, 72.0)
            )
            y_mm += 62.0 * breast_size * front_weight * vertical_weight * lateral_weight
        return (x_mm, y_mm, z_mm)

    if source_triangles:
        # Apply damped corrections at the named profile nodes. Each iteration
        # measures the actual deformed mesh contour, so target morphs, gender
        # shape, anisotropic scaling, and the soft torso mask are all included.
        profile_parameters = (
            ("hip", 0.50, 1.25),
            ("high_hip", 0.54, 1.20),
            ("waist", 0.58, 1.30),
            ("underbust", 0.64, 1.15),
            ("chest", 0.69, 1.15),
        )
        for _iteration in range(7):
            fitted_body = tuple(transform(point) for point in body)
            section_mesh = trimesh.Trimesh(
                vertices=np.asarray(fitted_body, dtype=np.float64),
                faces=np.asarray(source_triangles, dtype=np.int64),
                process=False,
            )
            max_relative_error = 0.0
            for index, (name, normalized_height, lateral_exponent) in enumerate(
                profile_parameters, start=1
            ):
                requested = float(parameters.measurement(name))
                contour_limit = max(
                    520.0,
                    2.0 * _profile_scale(normalized_height, core_width_profile) + 250.0,
                )
                actual = _section_circumference(
                    section_mesh,
                    normalized_height * height_mm,
                    vertical_axis=2,
                    max_width=contour_limit,
                )
                if actual <= 1e-6 or requested <= 0.0:
                    continue
                relative_error = (requested - actual) / requested
                max_relative_error = max(max_relative_error, abs(relative_error))
                correction = max(0.70, min(1.43, requested / actual))
                current_x = measurement_profile_x[index][1]
                current_y = measurement_profile_y[index][1]
                measurement_profile_x[index] = (
                    normalized_height,
                    max(0.45, min(2.25, current_x * correction**lateral_exponent)),
                )
                measurement_profile_y[index] = (
                    normalized_height,
                    max(0.45, min(2.25, current_y * correction ** (2.0 - lateral_exponent))),
                )
            if max_relative_error <= 0.002:
                break

    return transform


def _authored_arm_rig_points(parameters: AvatarParameters) -> dict[float, dict[str, Point]]:
    """Return fitted shoulder and wrist positions from authored MakeHuman bones.

    Args:
        parameters: Authoritative avatar measurements used to fit the source mesh.

    Returns:
        Left/right mappings with fitted shoulder and wrist coordinates.

    Raises:
        HumanoidMeshError: If required bones or their source vertices are missing.
    """
    source = apply_measurement_targets(_load_source_vertices(), parameters)
    skeleton = load_makehuman_skeleton()
    triangles = load_makehuman_mesh().triangles
    transform = _make_source_fitted_mapper(source, parameters, 0.0, source_triangles=triangles)
    points = {}
    for physical_side, suffix in ((-1.0, ".L"), (1.0, ".R")):
        shoulder = _bone_source_endpoints(
            source, skeleton, "upperarm01" + suffix, mapper=transform
        )[0]
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
    """Fit HM08 and pose arms using source-authored bones and skinning weights.

    Args:
        mesh: Validated source mesh and triangle topology.
        parameters: Authoritative anthropometric measurements and pose controls.
        arm_weights: Optional per-vertex left/right arm-chain influence arrays.

    Returns:
        Fitted and posed mesh with source topology preserved.

    Raises:
        HumanoidMeshError: If mesh, authored rig data, or fitted geometry is invalid.
    """
    mesh.validate()
    height_mm = float(parameters.measurement("height"))
    source_vertices = apply_measurement_targets(mesh.vertices, parameters)
    transform = _make_source_fitted_mapper(
        source_vertices,
        parameters,
        float(parameters.skin_offset),
        source_triangles=(
            mesh.triangles if len(mesh.vertices) >= MAKEHUMAN_BODY_VERTEX_COUNT else None
        ),
    )
    fitted = tuple(transform(point) for point in source_vertices)

    pose = parameters.pose
    shoulder_half = float(parameters.measurement("shoulder")) / 2.0
    shoulder_z = height_mm * 0.76
    shoulder_pivots = _estimate_shoulder_pivots(fitted, shoulder_half, height_mm)
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
    left_pose_angle = pose.left_arm_angle
    right_pose_angle = pose.right_arm_angle
    if left_pose_angle is None or right_pose_angle is None:
        from freecad_cloth.avatar.AvatarModel import DEFAULT_POSE_ARM_ANGLES

        default_pose_angle = DEFAULT_POSE_ARM_ANGLES.get(
            pose.preset, DEFAULT_POSE_ARM_ANGLES["standing"]
        )
        if left_pose_angle is None:
            left_pose_angle = default_pose_angle
        if right_pose_angle is None:
            right_pose_angle = default_pose_angle
    left_angle = (
        default_angle
        if pose.preset != "standing" and left_pose_angle == 12.0
        else float(left_pose_angle)
    )
    right_angle = (
        default_angle
        if pose.preset != "standing" and right_pose_angle == 12.0
        else float(right_pose_angle)
    )
    posed = []
    for index, (x, y, z) in enumerate(fitted):
        side = -1.0 if x < 0.0 else 1.0
        pivot_x = shoulder_pivots.get(side, side * shoulder_half)
        source_weight = None if arm_weights is None else arm_weights[0 if side < 0 else 1][index]
        weight = arm_pose_weight(x, z, pivot_x, height_mm, source_weight)
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


def arm_pose_weight(
    x: float,
    z: float,
    shoulder_pivot_x: float,
    height_mm: float,
    source_weight: float | None = None,
) -> float:
    """Return normalized arm-chain influence for one fitted mesh vertex.

    Authored skin weights are authoritative when provided. Otherwise, lateral
    distance from the shoulder pivot and normalized vertex height produce a
    smooth geometric fallback.

    Args:
        x: Vertex X coordinate in millimetres.
        z: Vertex height in millimetres.
        shoulder_pivot_x: Shoulder pivot X coordinate in millimetres.
        height_mm: Fitted mannequin height used to normalize vertex height.
        source_weight: Optional authored arm-chain influence.

    Returns:
        A finite influence value between zero and one.
    """
    if source_weight is not None:
        return max(0.0, min(1.0, float(source_weight)))
    pivot = abs(shoulder_pivot_x)
    lateral = _smoothstep(pivot * 0.98, pivot * 1.12, abs(x))
    nz = z / max(1.0, height_mm)
    # The articulated hand/wrist can hang well below chest height; keep the
    # the estimated influence active through the lower arm envelope while preserving
    # the upper torso cutoff.
    vertical = _smoothstep(0.28, 0.34, nz) * (1.0 - _smoothstep(0.88, 0.96, nz))
    return lateral * vertical


def build_humanoid_mesh(
    parameters: AvatarParameters, source_path: str | os.PathLike[str] | None = None
) -> MeshData:
    """Load and fit the pinned MakeHuman mannequin for Cloth.

    Args:
        parameters: Authoritative mannequin measurements and pose settings.
        source_path: Optional explicit mesh path for controlled imports or tests.

    Returns:
        Fitted, posed humanoid mesh in FreeCAD coordinates.

    Raises:
        HumanoidMeshError: If the source mesh cannot be loaded, validated, or fitted.
    """
    source = load_makehuman_mesh(str(source_path) if source_path is not None else None)
    arm_weights = (
        None if source_path is not None else load_makehuman_arm_weights(len(source.vertices))
    )
    return fit_makehuman_mesh(source, parameters, arm_weights=arm_weights)

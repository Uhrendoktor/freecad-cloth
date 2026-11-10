# Copyright (C) 2026 FreeCAD Cloth contributors
"""MakeHuman HM08 sparse morph-target parsing and application.

Target files contain sparse per-vertex displacements. The assets remain
external because MakeHuman distributes them separately from this workbench.
Both loose targets and MakeHuman's targets.npz archive are supported.
"""

from __future__ import annotations

import gzip
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

import numpy as np
from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.avatar.avatar_defaults import DEFAULT_MEASUREMENTS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

Point = tuple[float, float, float]

TARGETS_ENV = "FREECAD_CLOTH_MAKEHUMAN_TARGETS"
_TARGET_ROW_FIELD_COUNT = 4
_VECTOR_ARRAY_RANK = 2
_VECTOR_COMPONENT_COUNT = 3
_MIN_TARGET_WEIGHT = 1e-12


class _AvatarTargetParameters(Protocol):
    """Structural avatar settings consumed when deriving morph-target weights."""

    gender: float
    breast_size: float

    def measurement(self, name: str) -> float:
        """Return one validated anthropometric measurement in millimetres.

        Args:
            name: Canonical measurement key requested by the target selector.

        Returns:
            The selected measurement value in millimetres.
        """


@pydantic_dataclass(frozen=True)
class MakeHumanTarget:
    """Sparse vertex offsets read from a MakeHuman target."""

    name: str
    offsets: tuple[tuple[int, Point], ...]


@pydantic_dataclass(frozen=True)
class TargetReference:
    """Address a loose target file or one target inside a targets.npz archive."""

    path: Path
    archive_key: str | None = None
    coordinate_format: Literal["makehuman", "mpfb2"] = "makehuman"


def parse_target(
    text: str,
    name: str = "<memory>",
    coordinate_format: Literal["makehuman", "mpfb2"] = "makehuman",
) -> MakeHumanTarget:
    """Parse sparse target rows in native MakeHuman or MPFB2 coordinate order.

    MakeHuman source targets use native X/Y/Z offsets. MPFB2 stores equivalent
    target rows as X/Z/-Y for its Blender-oriented HM08 mesh. The selected
    format is inferred from the target-library layout by the resolver.

    Args:
        text: Target file contents containing sparse vertex-index/displacement rows.
        name: Source name included in parse errors and stored on the returned target.
        coordinate_format: Coordinate convention used by the source target library.

    Returns:
        A target containing sorted vertex indices and accumulated 3D offsets.

    Raises:
        ValueError: If a row is malformed, has a negative vertex index, or
            contains non-finite offsets.
    """
    collected: dict[int, Point] = {}
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", '"')):
            continue
        fields = line.split()
        if len(fields) < _TARGET_ROW_FIELD_COUNT:
            msg = f"{name}:{line_number}: target row needs four fields"
            raise ValueError(msg)
        try:
            index = int(fields[0])
            first, second, third = float(fields[1]), float(fields[2]), float(fields[3])
            offset: Point = (
                (first, -third, second) if coordinate_format == "mpfb2" else (first, second, third)
            )
        except (TypeError, ValueError, OverflowError) as exc:
            msg = f"{name}:{line_number}: invalid target row"
            raise ValueError(msg) from exc
        if index < 0:
            msg = f"{name}:{line_number}: vertex index must be non-negative"
            raise ValueError(msg)
        if not all(math.isfinite(value) for value in offset):
            msg = f"{name}:{line_number}: offsets must be finite"
            raise ValueError(msg)
        prior = collected.get(index, (0.0, 0.0, 0.0))
        collected[index] = (
            prior[0] + offset[0],
            prior[1] + offset[1],
            prior[2] + offset[2],
        )
    return MakeHumanTarget(str(name), tuple(sorted(collected.items())))


@lru_cache(maxsize=256)
def _load_target_cached(
    path_text: str,
    modified_ns: int,
    size: int,
    archive_key: str | None,
    coordinate_format: Literal["makehuman", "mpfb2"],
) -> MakeHumanTarget:
    """Load a target from a loose file or an archive using its cache identity.

    Args:
        path_text: Absolute or relative path to the target source.
        modified_ns: Modification timestamp used to invalidate stale cache entries.
        size: Source file size used to invalidate stale cache entries.
        archive_key: Sparse target key prefix, or None for a loose target file.
        coordinate_format: Coordinate convention used by the target data.

    Returns:
        The parsed sparse target with duplicate vertex offsets combined.

    Raises:
        ValueError: If an archive target is incomplete or contains invalid arrays or values.
    """
    del modified_ns, size
    source = Path(path_text)
    if archive_key is None:
        if source.name.endswith(".gz"):
            with gzip.open(source, "rt", encoding="utf-8", errors="strict") as stream:
                payload = stream.read()
        else:
            payload = source.read_text(encoding="utf-8", errors="strict")
        return parse_target(payload, source.as_posix(), coordinate_format)

    with np.load(source, allow_pickle=False) as archive:
        index_key = f"{archive_key}.index"
        vector_key = f"{archive_key}.vector"
        if index_key not in archive or vector_key not in archive:
            msg = f"{source}: archive target is incomplete: {archive_key}"
            raise ValueError(msg)
        indices = archive[index_key]
        vectors = archive[vector_key]
        if (
            indices.ndim != 1
            or vectors.ndim != _VECTOR_ARRAY_RANK
            or vectors.shape[0] != indices.shape[0]
            or vectors.shape[1] != _VECTOR_COMPONENT_COUNT
        ):
            msg = f"{source}: archive target has invalid array shapes: {archive_key}"
            raise ValueError(msg)
        merged: dict[int, Point] = {}
        for raw_index, raw_vector in zip(indices, vectors, strict=True):
            index = int(raw_index)
            first, second, third = (float(value) * 1e-3 for value in raw_vector)
            offset: Point = (
                (first, -third, second) if coordinate_format == "mpfb2" else (first, second, third)
            )
            if index < 0 or not all(math.isfinite(value) for value in offset):
                msg = f"{source}: archive target has invalid values: {archive_key}"
                raise ValueError(msg)
            prior = merged.get(index, (0.0, 0.0, 0.0))
            merged[index] = (
                prior[0] + offset[0],
                prior[1] + offset[1],
                prior[2] + offset[2],
            )
    return MakeHumanTarget(f"{source.as_posix()}::{archive_key}", tuple(sorted(merged.items())))


def load_target(
    path: str | os.PathLike[str] | TargetReference,
) -> MakeHumanTarget:
    """Load a loose, gzip-compressed, or archived target.

    Args:
        path: File path or reference identifying the target to load.

    Returns:
        The parsed target with its sparse offsets in the selected coordinate convention.

    """
    if isinstance(path, TargetReference):
        source = path.path.expanduser().resolve()
        archive_key = path.archive_key
        coordinate_format = path.coordinate_format
    else:
        source = Path(path).expanduser().resolve()
        archive_key = None
        coordinate_format = _target_coordinate_format(source.parent)
    stat = source.stat()
    return _load_target_cached(
        source.as_posix(),
        stat.st_mtime_ns,
        stat.st_size,
        archive_key,
        coordinate_format,
    )


def _target_coordinate_format(root: Path) -> Literal["makehuman", "mpfb2"]:
    """Detect whether a target directory uses MakeHuman or MPFB2 coordinates.

    Args:
        root: Directory used as the starting point for metadata and layout checks.

    Returns:
        The coordinate format inferred from target metadata or directory names.
    """
    for parent in (root, *root.parents):
        if (parent / "target.json").is_file():
            return "mpfb2"
        if parent.name.casefold() in {"mpfb", "mpfb2"}:
            return "mpfb2"
    return "makehuman"


def target_directory(environ: Mapping[str, str] | None = None) -> Path | None:
    """Locate an installed MakeHuman target library or an archive-backed data directory.

    Set FREECAD_CLOTH_MAKEHUMAN_TARGETS to a targets directory, a MakeHuman
    data directory, or a checkout of makehuman-assets to select another library.

    Args:
        environ: Environment mapping to inspect, or None to use the current process environment.

    Returns:
        The first supported target directory found, or None when no library is installed.
    """
    settings = os.environ if environ is None else environ
    candidates: list[Path] = []
    configured = settings.get(TARGETS_ENV, "").strip()
    if configured:
        base = Path(configured).expanduser()
        candidates.extend(
            (base / "targets", base / "data" / "targets", base / "base" / "targets", base)
        )
    home = Path.home()
    configured_home = settings.get("MH_HOME_LOCATION", "").strip()
    if configured_home:
        custom_data = Path(configured_home).expanduser() / "v1py3" / "data"
        candidates.extend((custom_data / "targets", custom_data))
    local_app_data = settings.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        windows_data = Path(local_app_data) / "makehuman" / "v1py3" / "data"
        candidates.extend((windows_data / "targets", windows_data))
    candidates.extend(
        (
            home / "Documents" / "makehuman" / "v1py3" / "data" / "targets",
            home / "Documents" / "makehuman" / "v1py3" / "data",
            home / "makehuman" / "v1py3" / "data" / "targets",
            home / "makehuman" / "v1py3" / "data",
            home / "Documents" / "MakeHuman" / "v1py3" / "data" / "targets",
            home / "Library" / "Application Support" / "MakeHuman" / "v1py3" / "data",
            home / ".makehuman" / "data" / "targets",
            home / ".makehuman" / "v1py3" / "data" / "targets",
            home / ".cache" / "freecad-cloth" / "makehuman-targets",
            Path("/usr/share/makehuman-community/data/targets"),
            Path("/usr/share/makehuman-community/data"),
            Path("/usr/share/makehuman/data/targets"),
            Path("/usr/share/makehuman/data"),
            Path("/usr/local/share/makehuman/data/targets"),
            Path("/usr/local/share/makehuman/data"),
            Path("/Applications/MakeHuman.app/Contents/Resources/data/targets"),
            Path("/Applications/MakeHuman.app/Contents/Resources/data"),
        )
    )
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.expanduser().resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_dir():
            continue
        if (candidate / "targets.npz").is_file():
            return candidate.resolve()
        # Loose target trees are generally shallow, but recurse to support
        # packaged installations that add a vendor directory around targets.
        if any(candidate.glob("*.target*")) or any(candidate.glob("*/*.target*")):
            return candidate.resolve()
        if any(candidate.rglob("*.target*")):
            return candidate.resolve()
    return None


@lru_cache(maxsize=16)
def _target_index(root_text: str) -> dict[str, str]:
    """Index loose target files by case-insensitive relative path and basename.

    Args:
        root_text: Target directory whose loose target files should be indexed.

    Returns:
        Mapping from normalized target aliases to their absolute file paths.
    """
    root = Path(root_text)
    index: dict[str, str] = {}
    files = sorted((*root.rglob("*.target"), *root.rglob("*.target.gz")))
    for path in files:
        relative = path.relative_to(root).as_posix()
        suffix = ".target.gz" if relative.endswith(".target.gz") else ".target"
        target_name = relative[: -len(suffix)]
        index.setdefault(target_name.casefold(), path.as_posix())
        index.setdefault(Path(target_name).name.casefold(), path.as_posix())
    return index


@lru_cache(maxsize=16)
def _archive_target_index(path_text: str, modified_ns: int, size: int) -> dict[str, str]:
    """Index sparse targets stored in a MakeHuman targets.npz archive.

    Args:
        path_text: Path to the compressed target archive.
        modified_ns: Modification timestamp used to invalidate stale cache entries.
        size: Archive file size used to invalidate stale cache entries.

    Returns:
        Mapping from normalized target aliases to archive key prefixes.
    """
    del modified_ns, size
    index: dict[str, str] = {}
    with np.load(path_text, allow_pickle=False) as archive:
        for key in archive.files:
            if not key.endswith(".index"):
                continue
            target_name = key[: -len(".index")]
            target_name = target_name.removeprefix("targets/")
            index.setdefault(target_name.casefold(), key[: -len(".index")])
            index.setdefault(Path(target_name).name.casefold(), key[: -len(".index")])
    return index


def resolve_target(name: str, root: str | os.PathLike[str] | None = None) -> TargetReference | None:
    """Resolve a target by relative path or basename, with or without extension.

    Args:
        name: Relative target name or basename, optionally including its extension.
        root: Target library root to search, or None to discover an installed library.

    Returns:
        A reference to the matching loose or archived target, or None when it is absent.
    """
    base = Path(root).expanduser().resolve() if root is not None else target_directory()
    if base is None or not base.is_dir():
        return None
    cleaned = str(name).replace("\\", "/").strip().lstrip("/")
    if ".." in Path(cleaned).parts:
        return None
    for suffix in (".target.gz", ".target"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    for path in (base / f"{cleaned}.target", base / f"{cleaned}.target.gz"):
        if path.is_file():
            return TargetReference(
                path.resolve(), coordinate_format=_target_coordinate_format(base)
            )
    indexed_path = _target_index(base.as_posix()).get(cleaned.casefold())
    if indexed_path is not None:
        return TargetReference(
            Path(indexed_path), coordinate_format=_target_coordinate_format(base)
        )
    archive_candidates = (base / "targets.npz", base.parent / "targets.npz")
    for archive_path in archive_candidates:
        if not archive_path.is_file():
            continue
        stat = archive_path.stat()
        archive_targets = _archive_target_index(
            archive_path.as_posix(), stat.st_mtime_ns, stat.st_size
        )
        archive_key = archive_targets.get(cleaned.casefold())
        if archive_key is None:
            archive_key = archive_targets.get(cleaned.removeprefix("targets/").casefold())
        if archive_key is not None:
            return TargetReference(
                archive_path,
                archive_key,
                _target_coordinate_format(base),
            )
    return None


def apply_targets(
    vertices: Sequence[Point],
    weights: Mapping[str, float],
    root: str | os.PathLike[str] | None = None,
) -> tuple[Point, ...]:
    """Blend sparse target deltas onto vertices without changing topology.

    Target indices outside the supplied mesh are ignored because HM08's source
    OBJ may contain helper vertices after the visible body surface.

    Args:
        vertices: Original mesh coordinates in vertex-index order.
        weights: Target names and their signed blend strengths.
        root: Target library root to search, or None to discover an installed library.

    Returns:
        Updated mesh coordinates in their original vertex-index order.

    Raises:
        ValueError: If a supplied target weight is not finite.
    """
    base = Path(root).expanduser().resolve() if root is not None else target_directory()
    if base is None:
        return tuple((float(p[0]), float(p[1]), float(p[2])) for p in vertices)
    mutable = [[float(value) for value in point] for point in vertices]
    for name, weight_value in weights.items():
        weight = float(weight_value)
        if not math.isfinite(weight):
            msg = f"target weight for {name!r} must be finite"
            raise ValueError(msg)
        if abs(weight) < _MIN_TARGET_WEIGHT:
            continue
        source = resolve_target(name, base)
        if source is None:
            continue
        target = load_target(source)
        for index, offset in target.offsets:
            if index >= len(mutable):
                continue
            point = mutable[index]
            point[0] += weight * offset[0]
            point[1] += weight * offset[1]
            point[2] += weight * offset[2]
    return tuple((point[0], point[1], point[2]) for point in mutable)


def apply_measurement_targets(
    vertices: Sequence[Point],
    parameters: _AvatarTargetParameters,
    *,
    target_root: Path | None = None,
) -> tuple[Point, ...]:
    """Apply compatible MakeHuman targets before exact circumference fitting.

    Directional measurement targets improve local anatomy; the mesh fitter then
    corrects torso circumference contours in millimetres. Target shape quality
    is additive and does not override numeric torso measurements.

    Args:
        vertices: Original mesh coordinates in vertex-index order.
        parameters: Validated avatar parameters that select directional targets.
        target_root: Optional target library root; None triggers installed-library discovery.

    Returns:
        Mesh coordinates after applying the selected sparse measurement targets.
    """
    root = target_directory() if target_root is None else target_root
    if root is None:
        return tuple((float(p[0]), float(p[1]), float(p[2])) for p in vertices)

    weights: dict[str, float] = {}
    gender = float(parameters.gender)
    female_name = "macrodetails/gender/female"
    male_name = "macrodetails/gender/male"
    if resolve_target(female_name, root) and resolve_target(male_name, root):
        weights[female_name] = 1.0 - gender
        weights[male_name] = gender

    breast_size = float(parameters.breast_size)
    if breast_size > 0:
        breast_name = "breast/breast-volume-vert-up"
        if resolve_target(breast_name, root):
            weights[breast_name] = breast_size

    measurement_targets = (
        ("hip", "measure-hips-circ"),
        ("waist", "measure-waist-circ"),
        ("underbust", "measure-underbust-circ"),
        ("chest", "measure-bust-circ"),
        ("upper_arm", "measure-upperarm-circ"),
        ("wrist", "measure-wrist-circ"),
        ("thigh", "measure-thigh-circ"),
        ("knee", "measure-knee-circ"),
        ("calf", "measure-calf-circ"),
        ("ankle", "measure-ankle-circ"),
        ("neck", "measure-neck-circ"),
    )
    for parameter_name, target_base in measurement_targets:
        default = float(DEFAULT_MEASUREMENTS[parameter_name])
        desired = float(parameters.measurement(parameter_name))
        if math.isclose(desired, default, rel_tol=0.0, abs_tol=1e-9):
            continue
        direction = "incr" if desired > default else "decr"
        target_name = f"{target_base}-{direction}"
        strength = min(1.0, abs(desired / default - 1.0) / 0.25)
        if resolve_target(target_name, root):
            weights[target_name] = strength
    return apply_targets(vertices, weights, root)

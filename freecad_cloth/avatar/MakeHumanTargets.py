"""MakeHuman HM08 morph-target parsing and application.

Target files contain sparse vertex offsets, not standalone meshes. This module
keeps target assets external (they have their own distribution/licensing) while
supporting the complete target-file format for a matching HM08 base mesh.
"""

from __future__ import annotations

import gzip
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

Point = tuple[float, float, float]
TARGETS_ENV = "FREECAD_CLOTH_MAKEHUMAN_TARGETS"


@dataclass(frozen=True)
class MakeHumanTarget:
    """Sparse vertex offsets read from a MakeHuman target file."""

    name: str
    offsets: tuple[tuple[int, Point], ...]


def parse_target(text: str, name: str = "<memory>") -> MakeHumanTarget:
    """Parse sparse X-Z-Y offsets into HM08 source-axis X/Y/Z coordinates.

    Target rows store vertex index, X offset, Z offset, and sign-inverted Y
    offset. The source mesh uses MakeHuman's native Y-up coordinates.
    """
    collected: dict[int, Point] = {}
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith('"'):
            continue
        fields = line.split()
        if len(fields) < 4:
            raise ValueError(f"{name}:{line_number}: target row needs four fields")
        try:
            index = int(fields[0])
            dx = float(fields[1])
            dz = float(fields[2])
            dy = -float(fields[3])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name}:{line_number}: invalid target row") from exc
        if index < 0:
            raise ValueError(f"{name}:{line_number}: vertex index must be non-negative")
        offset = (dx, dy, dz)
        if not all(math.isfinite(value) for value in offset):
            raise ValueError(f"{name}:{line_number}: offsets must be finite")
        prior = collected.get(index, (0.0, 0.0, 0.0))
        collected[index] = tuple(prior[axis] + offset[axis] for axis in range(3))
    return MakeHumanTarget(str(name), tuple(sorted(collected.items())))


@lru_cache(maxsize=256)
def _load_target_cached(path: str, modified_ns: int, size: int) -> MakeHumanTarget:
    del modified_ns, size
    source = Path(path)
    if source.name.endswith(".gz"):
        with gzip.open(source, "rt", encoding="utf-8", errors="strict") as stream:
            payload = stream.read()
    else:
        payload = source.read_text(encoding="utf-8", errors="strict")
    return parse_target(payload, source.as_posix())


def load_target(path: str | os.PathLike[str]) -> MakeHumanTarget:
    """Load a plain or gzip-compressed target, invalidating cache on file change."""
    source = Path(path).expanduser().resolve()
    stat = source.stat()
    return _load_target_cached(source.as_posix(), stat.st_mtime_ns, stat.st_size)


def target_directory() -> Path | None:
    """Resolve a compatible MakeHuman/MPFB2 target library, if installed.

    Set FREECAD_CLOTH_MAKEHUMAN_TARGETS to a target directory, a data directory,
    or a checkout of makehuman-assets. Target files are not vendored because
    they are distributed separately from code.
    """
    candidates: list[Path] = []
    configured = os.environ.get(TARGETS_ENV, "").strip()
    if configured:
        base = Path(configured).expanduser()
        candidates.extend((base, base / "targets", base / "data" / "targets", base / "base" / "targets"))
    home = Path.home()
    candidates.extend(
        (
            home / ".makehuman" / "data" / "targets",
            home / ".makehuman" / "v1py3" / "data" / "targets",
            home / ".cache" / "freecad-cloth" / "makehuman-targets",
            Path("/usr/share/makehuman/data/targets"),
            Path("/usr/local/share/makehuman/data/targets"),
        )
    )
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.expanduser().resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_dir() and any(candidate.glob("*.target*")):
            return candidate.resolve()
    return None


@lru_cache(maxsize=16)
def _target_index(root_text: str) -> dict[str, str]:
    root = Path(root_text)
    index: dict[str, str] = {}
    files = sorted((*root.rglob("*.target"), *root.rglob("*.target.gz")))
    for path in files:
        relative = path.relative_to(root).as_posix()
        suffix = ".target.gz" if relative.endswith(".target.gz") else ".target"
        target_name = relative[:-len(suffix)]
        index.setdefault(target_name.casefold(), path.as_posix())
        index.setdefault(Path(target_name).name.casefold(), path.as_posix())
    return index


def resolve_target(name: str, root: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve a target by relative path or basename, with or without extension."""
    base = Path(root).expanduser().resolve() if root is not None else target_directory()
    if base is None or not base.is_dir():
        return None
    cleaned = str(name).replace("\\", "/").strip().lstrip("/")
    for suffix in (".target.gz", ".target"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break
    for path in (base / f"{cleaned}.target", base / f"{cleaned}.target.gz"):
        if path.is_file():
            return path.resolve()
    indexed = _target_index(base.as_posix()).get(cleaned.casefold())
    return Path(indexed) if indexed is not None else None


def apply_targets(
    vertices: Sequence[Point],
    weights: Mapping[str, float],
    root: str | os.PathLike[str] | None = None,
) -> tuple[Point, ...]:
    """Blend sparse target deltas onto vertices without changing topology.

    Target indices outside the supplied mesh are ignored: HM08's source OBJ
    includes helper vertices after the visible 13,380-vertex body surface.
    """
    base = Path(root).expanduser().resolve() if root is not None else target_directory()
    if base is None:
        return tuple((float(p[0]), float(p[1]), float(p[2])) for p in vertices)
    mutable = [[float(value) for value in point] for point in vertices]
    for name, weight_value in weights.items():
        weight = float(weight_value)
        if not math.isfinite(weight):
            raise ValueError(f"target weight for {name!r} must be finite")
        if abs(weight) < 1e-12:
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


def apply_measurement_targets(vertices: Sequence[Point], parameters: object) -> tuple[Point, ...]:
    """Apply compatible body targets before exact circumference fitting.

    Directional measurement targets improve local anatomy; the mesh fitter then
    corrects their final circumference in millimetres. Target shape quality is
    additive and does not override numeric measurements.
    """
    root = target_directory()
    if root is None:
        return tuple((float(p[0]), float(p[1]), float(p[2])) for p in vertices)

    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

    weights: dict[str, float] = {}
    gender = float(getattr(parameters, "gender", 0.5))
    female_name = "macrodetails/gender/female"
    male_name = "macrodetails/gender/male"
    if resolve_target(female_name, root) and resolve_target(male_name, root):
        weights[female_name] = 1.0 - gender
        weights[male_name] = gender

    breast_size = float(getattr(parameters, "breast_size", 0.0))
    if breast_size > 0:
        breast_name = "breast/breast-dist-incr"
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
    measurement = getattr(parameters, "measurement")
    for parameter_name, target_base in measurement_targets:
        default = float(DEFAULT_MEASUREMENTS[parameter_name])
        desired = float(measurement(parameter_name))
        if math.isclose(desired, default, rel_tol=0.0, abs_tol=1e-9):
            continue
        direction = "incr" if desired > default else "decr"
        target_name = f"{target_base}-{direction}"
        strength = min(1.0, abs(desired / default - 1.0) / 0.25)
        if resolve_target(target_name, root):
            weights[target_name] = strength
    return apply_targets(vertices, weights, root)

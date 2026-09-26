"""Deterministic solver-neutral rigid garment placement against a DrapeTarget.

The module deliberately contains no FreeCAD or solver imports.  It consumes the
persisted CollisionSurface representation and returns bounded rigid translations
plus diagnostics.  Placement application and document persistence live in the
fitting command layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Mapping, Sequence, Tuple

from freecad_cloth.avatar.AvatarCollision import CollisionSurface

Point3 = Tuple[float, float, float]
_WRAP_VECTORS = {
    "front": (0.0, -1.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}


class TargetPlacementError(ValueError):
    """Fail-closed placement contract error."""


@dataclass(frozen=True)
class PlacementAnchor:
    name: str
    local_position: Point3
    wrap_direction: str
    weight: float = 1.0

    def validate(self) -> None:
        if not self.name.strip():
            raise TargetPlacementError("placement anchor name must not be empty")
        if self.wrap_direction not in _WRAP_VECTORS:
            raise TargetPlacementError("unsupported anchor wrap direction: %s" % self.wrap_direction)
        if len(self.local_position) != 3:
            raise TargetPlacementError("placement anchor requires three coordinates")
        if float(self.weight) <= 0.0:
            raise TargetPlacementError("placement anchor weight must be positive")


@dataclass(frozen=True)
class SurfaceProbe:
    point: Point3
    normal: Point3
    distance: float
    triangle_index: int


@dataclass(frozen=True)
class RigidPlacementSolution:
    translation: Point3
    rotation_degrees: float
    minimum_anchor_clearance: float
    maximum_anchor_residual: float
    probes: Tuple[SurfaceProbe, ...]


@dataclass(frozen=True)
class TunicAnchorProfile:
    anchors: Tuple[PlacementAnchor, ...]
    primary_wrap_direction: str

    def validate(self) -> None:
        if self.primary_wrap_direction not in _WRAP_VECTORS:
            raise TargetPlacementError("unsupported primary wrap direction: %s" % self.primary_wrap_direction)
        if not self.anchors:
            raise TargetPlacementError("at least one garment anchor is required")
        names = set()
        for anchor in self.anchors:
            anchor.validate()
            if anchor.name in names:
                raise TargetPlacementError("placement anchor names must be unique")
            names.add(anchor.name)


def tunic_anchor_profile(width: float, height: float, primary_wrap_direction: str) -> TunicAnchorProfile:
    """Return deterministic shoulder/side/waist anchors for a flat tunic panel."""
    if float(width) <= 0.0 or float(height) <= 0.0:
        raise TargetPlacementError("tunic anchor dimensions must be positive")
    if primary_wrap_direction not in ("front", "back"):
        raise TargetPlacementError("tunic primary wrap direction must be front or back")
    w = float(width)
    h = float(height)
    profile = TunicAnchorProfile(
        anchors=(
            PlacementAnchor("shoulder_left", (0.14 * w, 0.97 * h, 0.0), "left", 1.5),
            PlacementAnchor("shoulder_right", (0.86 * w, 0.97 * h, 0.0), "right", 1.5),
            PlacementAnchor("side_left", (0.02 * w, 0.55 * h, 0.0), "left", 1.0),
            PlacementAnchor("side_right", (0.98 * w, 0.55 * h, 0.0), "right", 1.0),
            PlacementAnchor("waist", (0.50 * w, 0.55 * h, 0.0), primary_wrap_direction, 1.5),
        ),
        primary_wrap_direction=primary_wrap_direction,
    )
    profile.validate()
    return profile


def wrap_vector(direction: str) -> Point3:
    try:
        return _WRAP_VECTORS[str(direction)]
    except KeyError as exc:
        raise TargetPlacementError("unsupported wrap direction: %s" % direction) from exc


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Point3, b: Point3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Point3, scale: float) -> Point3:
    return (a[0] * scale, a[1] * scale, a[2] * scale)


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Point3) -> float:
    return sqrt(_dot(a, a))


def _normalize(a: Point3) -> Point3:
    length = _norm(a)
    if length <= 1e-12:
        raise TargetPlacementError("zero-length target normal")
    return _scale(a, 1.0 / length)


def _distance(a: Point3, b: Point3) -> float:
    return _norm(_sub(a, b))


def _triangle_normal(surface: CollisionSurface, triangle_index: int) -> Point3:
    ia, ib, ic = surface.triangles[triangle_index]
    a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
    normal = _normalize(_cross(_sub(b, a), _sub(c, a)))
    center = surface.center
    centroid = _scale(_add(_add(a, b), c), 1.0 / 3.0)
    if _dot(normal, _sub(centroid, center)) < 0.0:
        normal = _scale(normal, -1.0)
    return normal


def _closest_point_on_triangle(point: Point3, a: Point3, b: Point3, c: Point3) -> Point3:
    ab = _sub(b, a)
    ac = _sub(c, a)
    ap = _sub(point, a)
    d1 = _dot(ab, ap)
    d2 = _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = _sub(point, b)
    d3 = _dot(ab, bp)
    d4 = _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        denom = d1 - d3
        return _add(a, _scale(ab, d1 / denom if abs(denom) > 1e-12 else 0.0))
    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denom = d2 - d6
        return _add(a, _scale(ac, d2 / denom if abs(denom) > 1e-12 else 0.0))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        denom = (d4 - d3) + (d5 - d6)
        bc = _sub(c, b)
        return _add(b, _scale(bc, (d4 - d3) / denom if abs(denom) > 1e-12 else 0.0))
    denom = va + vb + vc
    if abs(denom) <= 1e-12:
        return _scale(_add(_add(a, b), c), 1.0 / 3.0)
    inv = 1.0 / denom
    v = vb * inv
    w = vc * inv
    return _add(a, _add(_scale(ab, v), _scale(ac, w)))


def probe_target(
    surface: CollisionSurface,
    point: Point3,
    wrap_direction: str | None = None,
    *,
    ambiguity_tolerance: float = 0.25,
    reject_ambiguous: bool = True,
) -> SurfaceProbe:
    """Find one deterministic outward surface probe; reject contradictory ties."""
    surface.validate()
    expected = wrap_vector(wrap_direction) if wrap_direction is not None else None
    candidates = []
    for index, triangle in enumerate(surface.triangles):
        normal = _triangle_normal(surface, index)
        if expected is not None and _dot(normal, expected) < 0.10:
            continue
        a, b, c = (surface.vertices[int(i)] for i in triangle)
        closest = _closest_point_on_triangle(point, a, b, c)
        distance = _distance(point, closest)
        candidates.append((distance, index, closest, normal))
    if not candidates:
        raise TargetPlacementError("no target surface matches wrap direction %s" % wrap_direction)
    candidates.sort(key=lambda item: (item[0], item[1]))
    best_distance, best_index, best_point, best_normal = candidates[0]
    for distance, index, _, normal in candidates[1:]:
        if distance > best_distance + float(ambiguity_tolerance):
            break
        if reject_ambiguous and _dot(best_normal, normal) < 0.60:
            raise TargetPlacementError(
                "ambiguous target surface near anchor: triangles %d and %d disagree on outward side"
                % (best_index, index)
            )
    return SurfaceProbe(tuple(best_point), tuple(best_normal), float(best_distance), int(best_index))


def minimum_signed_clearance(
    points: Sequence[Point3],
    surface: CollisionSurface,
    *,
    sample_limit: int = 256,
) -> float | None:
    """Return the minimum outward-normal signed clearance.

    Positive values are outside the target; negative values indicate penetration.
    The optional deterministic sample limit bounds diagnostic cost in large GUI scenes.
    """
    surface.validate()
    if not points:
        return None
    limit = max(1, int(sample_limit))
    if len(points) > limit:
        stride = max(1, (len(points) - 1) // (limit - 1))
        sample = tuple(points[index] for index in range(0, len(points), stride))[:limit]
    else:
        sample = tuple(points)
    best = float("inf")
    for point in sample:
        probe = probe_target(surface, tuple(float(c) for c in point), reject_ambiguous=False)
        signed = _dot(_sub(point, probe.point), probe.normal) - float(surface.thickness)
        best = min(best, signed)
    return float(best)


def solve_rigid_translation(
    anchor_world_positions: Mapping[str, Point3],
    profile: TunicAnchorProfile,
    surface: CollisionSurface,
    *,
    clearance: float,
    max_translation: float,
    max_rotation_degrees: float,
    ambiguity_tolerance: float = 0.25,
) -> RigidPlacementSolution:
    """Solve a bounded deterministic rigid translation while preserving rotation."""
    profile.validate()
    surface.validate()
    if float(clearance) < 0.0:
        raise TargetPlacementError("clearance must not be negative")
    if float(max_translation) <= 0.0:
        raise TargetPlacementError("maximum translation must be positive")
    if float(max_rotation_degrees) < 0.0:
        raise TargetPlacementError("maximum rotation must not be negative")
    probes = []
    weighted_delta = (0.0, 0.0, 0.0)
    total_weight = 0.0
    for anchor in profile.anchors:
        if anchor.name not in anchor_world_positions:
            raise TargetPlacementError("missing world anchor: %s" % anchor.name)
        world = tuple(float(c) for c in anchor_world_positions[anchor.name])
        probe = probe_target(
            surface,
            world,
            anchor.wrap_direction,
            ambiguity_tolerance=ambiguity_tolerance,
        )
        desired = _add(probe.point, _scale(probe.normal, float(surface.thickness) + float(clearance)))
        delta = _sub(desired, world)
        weight = float(anchor.weight)
        weighted_delta = _add(weighted_delta, _scale(delta, weight))
        total_weight += weight
        probes.append(probe)
    translation = _scale(weighted_delta, 1.0 / total_weight)
    length = _norm(translation)
    if length > float(max_translation) + 1e-9:
        raise TargetPlacementError(
            "target-aware translation %.3f mm exceeds bound %.3f mm"
            % (length, float(max_translation))
        )

    def anchor_clearances(candidate: Point3) -> Tuple[float, float]:
        values = []
        for anchor, probe in zip(profile.anchors, probes):
            world = anchor_world_positions[anchor.name]
            moved = _add(world, candidate)
            desired_gap = _dot(_sub(moved, probe.point), probe.normal) - float(surface.thickness)
            values.append(desired_gap)
        return min(values), max(
            _distance(
                _add(anchor_world_positions[anchor.name], candidate),
                _add(probe.point, _scale(probe.normal, float(surface.thickness) + float(clearance))),
            )
            for anchor, probe in zip(profile.anchors, probes)
        )

    minimum_clearance, residual = anchor_clearances(translation)
    if minimum_clearance < float(clearance):
        outward = (0.0, 0.0, 0.0)
        for anchor, probe in zip(profile.anchors, probes):
            outward = _add(outward, _scale(probe.normal, float(anchor.weight)))
        outward = _normalize(outward)
        correction = float(clearance) - minimum_clearance
        candidate = _add(translation, _scale(outward, correction))
        if _norm(candidate) > float(max_translation) + 1e-9:
            raise TargetPlacementError("target-aware clearance requires an out-of-bounds translation")
        translation = candidate
        minimum_clearance, residual = anchor_clearances(translation)
    if minimum_clearance < float(clearance) - 1e-6:
        raise TargetPlacementError(
            "deterministic rigid placement cannot satisfy %.3f mm anchor clearance"
            % float(clearance)
        )
    return RigidPlacementSolution(
        translation=tuple(float(v) for v in translation),
        rotation_degrees=0.0,
        minimum_anchor_clearance=float(minimum_clearance),
        maximum_anchor_residual=float(residual),
        probes=tuple(probes),
    )


def signature_payload(
    target_signature: object,
    piece_ids: Iterable[str],
    profile: TunicAnchorProfile,
    *,
    clearance: float,
    max_translation: float,
    max_rotation_degrees: float,
    algorithm_version: str = "tunic-target-aware-rigid-v1",
) -> dict:
    profile.validate()
    return {
        "algorithm": str(algorithm_version),
        "target_signature": target_signature,
        "piece_ids": tuple(sorted(str(value) for value in piece_ids)),
        "clearance": float(clearance),
        "max_translation": float(max_translation),
        "max_rotation_degrees": float(max_rotation_degrees),
        "anchors": tuple(
            (
                anchor.name,
                tuple(float(c) for c in anchor.local_position),
                anchor.wrap_direction,
                float(anchor.weight),
            )
            for anchor in profile.anchors
        ),
    }

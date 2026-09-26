"""Deterministic, solver-neutral garment pre-arrangement around a fitting target.

The arrangement stage only chooses safe initial piece centers. Collision and drape
remain owned by the persistent DrapeTarget and simulation layers.
"""
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple


SIDE_NAMES = ("front", "back", "left", "right")


@dataclass(frozen=True)
class TargetEnvelope:
    """World-space target envelope plus authored vertical fitting landmarks."""

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    shoulder_z: float
    hip_z: float

    @property
    def center_x(self) -> float:
        return (self.xmin + self.xmax) * 0.5

    @property
    def center_y(self) -> float:
        return (self.ymin + self.ymax) * 0.5

    @property
    def center_z(self) -> float:
        return (self.shoulder_z + self.hip_z) * 0.5


def _as_float(value):
    return float(value)


def target_envelope(bounds, shoulder_z: Optional[float] = None, hip_z: Optional[float] = None) -> TargetEnvelope:
    """Build a validated fitting envelope from a world-space bounds tuple."""
    if len(bounds) != 6:
        raise ValueError("target bounds require xmin, xmax, ymin, ymax, zmin, zmax")
    xmin, xmax, ymin, ymax, zmin, zmax = tuple(_as_float(value) for value in bounds)
    if not xmin < xmax or not ymin < ymax or not zmin < zmax:
        raise ValueError("target bounds must have positive extents")
    height = zmax - zmin
    shoulder = zmin + 0.76 * height if shoulder_z is None else _as_float(shoulder_z)
    hip = zmin + 0.40 * height if hip_z is None else _as_float(hip_z)
    if not zmin <= hip < shoulder <= zmax:
        raise ValueError("fitting landmarks must lie inside target height")
    return TargetEnvelope(xmin, xmax, ymin, ymax, zmin, zmax, shoulder, hip)


def classify_piece_side(label: str, current_center: Tuple[float, float, float], target: TargetEnvelope) -> str:
    """Return a deterministic front/back/left/right release side for one piece."""
    text = str(label).strip().lower()
    for side in SIDE_NAMES:
        if side in text:
            return side
    x, y, _z = (float(value) for value in current_center)
    dx = x - target.center_x
    dy = y - target.center_y
    if abs(dy) >= abs(dx):
        return "front" if dy >= 0.0 else "back"
    return "right" if dx >= 0.0 else "left"


def arranged_center(side: str, target: TargetEnvelope, clearance: float) -> Tuple[float, float, float]:
    """Return the safe release center for a piece on one side of the target."""
    side = str(side).strip().lower()
    if side not in SIDE_NAMES:
        raise ValueError("unknown arrangement side: %s" % side)
    clearance = float(clearance)
    if clearance < 0.0:
        raise ValueError("arrangement clearance must not be negative")
    if side == "front":
        return target.center_x, target.ymax + clearance, target.center_z
    if side == "back":
        return target.center_x, target.ymin - clearance, target.center_z
    if side == "left":
        return target.xmin - clearance, target.center_y, target.center_z
    return target.xmax + clearance, target.center_y, target.center_z


def arrange_piece_centers(
    pieces: Iterable[Tuple[str, Tuple[float, float, float]]],
    target: TargetEnvelope,
    clearance: float = 8.0,
):
    """Map piece labels/current centers to deterministic world release centers."""
    result = {}
    for label, current_center in pieces:
        side = classify_piece_side(label, current_center, target)
        result[str(label)] = arranged_center(side, target, clearance)
    return result

"""Deterministic structural checks for avatar visual acceptance.

The checks are intentionally geometry-only and solver-neutral. They are useful
for deciding whether a generated avatar can meaningfully serve as a visual
reference target before a garment simulation is evaluated.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


class AvatarVisualSanityError(ValueError):
    """Raised when avatar geometry cannot satisfy visual acceptance invariants."""


@dataclass(frozen=True)
class AvatarVisualSanity:
    height: float
    width: float
    depth: float
    triangle_count: int
    lateral_height_ratio: float

    @property
    def state(self) -> str:
        return "Valid"


def inspect_avatar_mesh(vertices, triangles, *, expected_height=None, max_lateral_height_ratio=0.9):
    """Return machine-checkable bounds/scale facts for an avatar mesh.

    ``max_lateral_height_ratio`` rejects edge-on/collapsed captures where the
    widest horizontal span is implausibly close to the body height.
    """
    if not vertices or not triangles:
        raise AvatarVisualSanityError("avatar mesh is empty")
    if any(len(point) != 3 for point in vertices):
        raise AvatarVisualSanityError("avatar vertices must be 3D coordinates")
    vertex_count = len(vertices)
    if any(len(tri) != 3 or any(int(index) < 0 or int(index) >= vertex_count for index in tri) for tri in triangles):
        raise AvatarVisualSanityError("avatar mesh contains an invalid triangle index")

    mins = tuple(min(float(point[axis]) for point in vertices) for axis in range(3))
    maxs = tuple(max(float(point[axis]) for point in vertices) for axis in range(3))
    spans = tuple(maxs[axis] - mins[axis] for axis in range(3))
    height = max(spans)
    lateral = sorted(spans)[:2]
    width = lateral[1]
    depth = lateral[0]
    if not math.isfinite(height) or height <= 0.0:
        raise AvatarVisualSanityError("avatar bounds do not contain a positive dimension")
    if expected_height is not None:
        expected_height = float(expected_height)
        if expected_height <= 0.0:
            raise AvatarVisualSanityError("expected avatar height must be positive")
        if not math.isclose(height, expected_height, rel_tol=0.02, abs_tol=1.0):
            raise AvatarVisualSanityError(
                "avatar height %.3f differs from expected %.3f" % (height, expected_height)
            )

    ratio = width / height
    if ratio > float(max_lateral_height_ratio):
        raise AvatarVisualSanityError(
            "avatar lateral span %.3f is too large for height %.3f" % (width, height)
        )
    return AvatarVisualSanity(height, width, depth, len(triangles), ratio)

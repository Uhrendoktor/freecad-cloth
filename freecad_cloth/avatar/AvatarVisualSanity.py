# Copyright (C) 2026 FreeCAD Cloth contributors
"""Deterministic structural checks for avatar visual acceptance.

The checks are intentionally geometry-only and solver-neutral. They are useful
for deciding whether a generated avatar can meaningfully serve as a visual
reference target before a garment simulation is evaluated.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.MeshTopology import triangle_indices_are_valid
from freecad_cloth.common.ValidationModels import validate_finite_number


class AvatarVisualSanityError(ValueError):
    """Raised when avatar geometry cannot satisfy visual acceptance invariants."""


@pydantic_dataclass(frozen=True)
class AvatarVisualSanity:
    """Public data model or service class for AvatarVisualSanity."""

    height: float
    width: float
    depth: float
    triangle_count: int
    lateral_height_ratio: float

    @property
    def state(self) -> str:
        """Return the current state summary.

        Returns:
            The state label used by visual acceptance checks.
        """
        return "Valid"


def inspect_avatar_mesh(
    vertices: Sequence[Sequence[float]],
    triangles: Sequence[Sequence[int]],
    *,
    expected_height: float | None = None,
    max_lateral_height_ratio: float = 0.9,
) -> AvatarVisualSanity:
    """Return machine-checkable bounds and scale facts for an avatar mesh.

    FreeCAD cloth geometry is Z-up, so Z is the authoritative body-height
    axis. The horizontal coordinate spans independently describe width and
    depth; the lateral-height ratio rejects edge-on or collapsed meshes.

    Args:
        vertices: Vertex coordinates in FreeCAD's X, Y, Z coordinate order.
        triangles: Triangle vertex indices into the supplied vertex array.
        expected_height: Optional expected Z extent in millimetres.
        max_lateral_height_ratio: Maximum permitted width-to-height ratio.

    Returns:
        Validated bounds and mesh summary values.

    Raises:
        AvatarVisualSanityError: If coordinates, topology, or scale are invalid.
    """
    if len(vertices) == 0 or len(triangles) == 0:
        msg = "avatar mesh is empty"
        raise AvatarVisualSanityError(msg)
    try:
        coordinates = np.asarray(vertices, dtype=np.float64)
    except (OverflowError, TypeError, ValueError) as exc:
        msg = "avatar vertices must be finite 3D coordinates"
        raise AvatarVisualSanityError(msg) from exc
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        msg = "avatar vertices must be 3D coordinates"
        raise AvatarVisualSanityError(msg)
    if not bool(np.isfinite(coordinates).all()):
        msg = "avatar vertices must contain only finite coordinates"
        raise AvatarVisualSanityError(msg)
    vertex_count = len(coordinates)
    if not triangle_indices_are_valid(triangles, vertex_count):
        msg = "avatar mesh contains an invalid triangle index or connectivity"
        raise AvatarVisualSanityError(msg)
    faces = np.asarray(triangles, dtype=np.intp)

    minimums = np.min(coordinates, axis=0)
    maximums = np.max(coordinates, axis=0)
    spans = maximums - minimums
    if not bool(np.isfinite(spans).all()):
        msg = "avatar mesh bounds must be finite"
        raise AvatarVisualSanityError(msg)
    height = float(spans[2])
    width = max(float(spans[0]), float(spans[1]))
    depth = min(float(spans[0]), float(spans[1]))
    if not math.isfinite(height) or height <= 0.0:
        msg = "avatar Z bounds do not contain a positive height"
        raise AvatarVisualSanityError(msg)
    if expected_height is not None:
        try:
            expected_height = validate_finite_number(expected_height)
        except (TypeError, ValueError) as exc:
            msg = "expected avatar height must be positive and finite"
            raise AvatarVisualSanityError(msg) from exc
        if expected_height <= 0.0:
            msg = "expected avatar height must be positive and finite"
            raise AvatarVisualSanityError(msg)
        if not math.isclose(height, expected_height, rel_tol=0.02, abs_tol=1.0):
            msg = f"avatar height {height:.3f} differs from expected {expected_height:.3f}"
            raise AvatarVisualSanityError(msg)

    try:
        lateral_limit = validate_finite_number(max_lateral_height_ratio)
    except (TypeError, ValueError) as exc:
        msg = "maximum lateral-height ratio must be finite and positive"
        raise AvatarVisualSanityError(msg) from exc
    if lateral_limit <= 0.0:
        msg = "maximum lateral-height ratio must be finite and positive"
        raise AvatarVisualSanityError(msg)
    ratio = width / height
    if ratio > lateral_limit:
        msg = f"avatar lateral span {width:.3f} is too large for height {height:.3f}"
        raise AvatarVisualSanityError(msg)
    return AvatarVisualSanity(height, width, depth, len(faces), ratio)

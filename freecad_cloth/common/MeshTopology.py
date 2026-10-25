# Copyright (C) 2026 FreeCAD Cloth contributors
"""Vectorized mesh-connectivity checks shared by mesh value objects."""

from collections.abc import Sequence

import numpy as np


def triangle_indices_are_valid(
    triangles: Sequence[Sequence[int]],
    vertex_count: int,
) -> bool:
    """Return whether triangle connectivity is valid for the available vertices.

    Args:
        triangles: Triangle vertex indices, shaped as ``(n, 3)``.
        vertex_count: Number of vertices in the corresponding coordinate array.

    Returns:
        Whether all indices are integers in range and each triangle has three
        distinct vertices. Malformed array-like input returns ``False``.
    """
    try:
        faces = np.asarray(triangles)
        return (
            faces.shape == (len(triangles), 3)
            and np.issubdtype(faces.dtype, np.integer)
            and bool(((faces >= 0) & (faces < vertex_count)).all())
            and bool(
                (
                    (faces[:, 0] != faces[:, 1])
                    & (faces[:, 1] != faces[:, 2])
                    & (faces[:, 0] != faces[:, 2])
                ).all()
            )
        )
    except (TypeError, ValueError, OverflowError, IndexError):
        return False

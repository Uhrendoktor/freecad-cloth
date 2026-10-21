# Copyright (C) 2026 FreeCAD Cloth contributors
"""Hypothesis properties for library-backed geometry invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from freecad_cloth.common.MeshValidation import (
    nearest_surface_clearance,
    nearest_target_clearance,
)
from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh
from tests.support.assertions import require


@settings(max_examples=40, deadline=None)
@given(
    dx=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    dy=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    dz=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_closed_mesh_containment_is_translation_invariant(
    dx: float, dy: float, dz: float
) -> None:
    """Translating a closed target and its query points preserves containment results.

    Args:
        dx: Sampled translation along the X axis, in the range [-1000, 1000].
        dy: Sampled translation along the Y axis, in the range [-1000, 1000].
        dz: Sampled translation along the Z axis, in the range [-1000, 1000].
    """
    vertices: tuple[tuple[float, float, float], ...] = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
    )
    triangles: tuple[tuple[int, int, int], ...] = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    points: tuple[tuple[float, float, float], ...] = (
        (0.5, 0.5, 0.5),
        (1.5, 0.5, 0.5),
    )
    expected = points_inside_closed_mesh(points, vertices, triangles)
    translated_vertices: tuple[tuple[float, float, float], ...] = tuple(
        (x + dx, y + dy, z + dz) for x, y, z in vertices
    )
    translated_points: tuple[tuple[float, float, float], ...] = tuple(
        (x + dx, y + dy, z + dz) for x, y, z in points
    )
    require(
        condition=expected == (True, False),
        message="The reference cube must contain its center but not the exterior point.",
    )
    require(
        condition=points_inside_closed_mesh(translated_points, translated_vertices, triangles)
        == expected,
        message="Translating the closed mesh and query points must preserve containment.",
    )


@settings(max_examples=40, deadline=None)
@given(
    dx=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    dy=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    dz=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_nearest_vertex_clearance_is_translation_invariant(
    dx: float, dy: float, dz: float
) -> None:
    """Translating both vertex sets preserves their nearest distance.

    Args:
        dx: Sampled translation along the X axis, in the range [-1000, 1000].
        dy: Sampled translation along the Y axis, in the range [-1000, 1000].
        dz: Sampled translation along the Z axis, in the range [-1000, 1000].
    """
    garment: tuple[tuple[float, float, float], ...] = (
        (0.0, 0.0, 2.0),
        (4.0, 0.0, 2.0),
        (4.0, 3.0, 2.0),
    )
    target: tuple[tuple[float, float, float], ...] = (
        (0.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.0, 3.0, 0.0),
    )
    distance = nearest_target_clearance(garment, target)
    shifted_garment: tuple[tuple[float, float, float], ...] = tuple(
        (x + dx, y + dy, z + dz) for x, y, z in garment
    )
    shifted_target: tuple[tuple[float, float, float], ...] = tuple(
        (x + dx, y + dy, z + dz) for x, y, z in target
    )
    require(
        condition=nearest_target_clearance(shifted_garment, shifted_target)
        == pytest.approx(distance, rel=1e-9, abs=1e-9),
        message="A shared translation must preserve nearest-target clearance.",
    )


@settings(max_examples=40, deadline=None)
@given(
    dx=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    dy=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    dz=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_nearest_surface_clearance_is_translation_invariant(
    dx: float, dy: float, dz: float
) -> None:
    """Translating a query point and target surface preserves their distance.

    Args:
        dx: Sampled translation along the X axis, in the range [-1000, 1000].
        dy: Sampled translation along the Y axis, in the range [-1000, 1000].
        dz: Sampled translation along the Z axis, in the range [-1000, 1000].
    """
    point: tuple[tuple[float, float, float], ...] = ((5.0, 5.0, 3.0),)
    vertices: tuple[tuple[float, float, float], ...] = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
    )
    triangles: tuple[tuple[int, int, int], ...] = ((0, 1, 2), (0, 2, 3))
    distance = nearest_surface_clearance(point, vertices, triangles)
    require(
        condition=distance == pytest.approx(3.0, rel=0.0, abs=1e-9),
        message="The point three units above the target must report that clearance.",
    )
    translated_point: tuple[tuple[float, float, float], ...] = tuple(
        (x + dx, y + dy, z + dz) for x, y, z in point
    )
    translated_vertices: tuple[tuple[float, float, float], ...] = tuple(
        (x + dx, y + dy, z + dz) for x, y, z in vertices
    )
    require(
        condition=nearest_surface_clearance(
            translated_point, translated_vertices, triangles
        )
        == pytest.approx(distance, rel=1e-8, abs=1e-8),
        message="A shared translation must preserve nearest-surface clearance.",
    )

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for mesh validation and nearest-surface measurements."""

import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from freecad_cloth.common.MeshValidation import (
    nearest_surface_clearance,
    nearest_target_clearance,
    nearest_target_observation,
    validate_mesh,
)

SQUARE_VERTEX_COUNT = 4
SQUARE_FACE_COUNT = 2
CONNECTED_COMPONENT_COUNT = 1
DISCONNECTED_COMPONENT_COUNT = 2
NO_DEGENERATE_FACES = 0
ONE_DEGENERATE_FACE = 1
SQUARE_SURFACE_AREA = 100.0
RIGHT_TRIANGLE_SURFACE_AREA = 6.0
ZERO_SURFACE_AREA = 0.0

type Point3 = tuple[float, float, float]
type Triangle = tuple[int, int, int]
type MeshFixture = tuple[tuple[Point3, ...], tuple[Triangle, ...]]


def square_mesh() -> MeshFixture:
    """Build the square mesh used by deterministic validation tests.

    Returns:
        Four square vertices and two triangles covering the square.
    """
    vertices = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
    )
    triangles = ((0, 1, 2), (0, 2, 3))
    return vertices, triangles


def test_validation_fallback_is_deterministic() -> None:
    """Validate the stable summary returned by the mesh fallback path."""
    vertices, triangles = square_mesh()
    result = validate_mesh(vertices, triangles, prefer_trimesh=False)
    assert result.vertices == SQUARE_VERTEX_COUNT, "fallback should count four vertices"
    assert result.faces == SQUARE_FACE_COUNT, "fallback should count two faces"
    assert result.components == CONNECTED_COMPONENT_COUNT, (
        "connected square should be one component"
    )
    assert result.bounds == (0.0, 10.0, 0.0, 10.0, 0.0, 0.0), (
        "fallback should preserve the square bounds"
    )
    assert result.surface_area == pytest.approx(SQUARE_SURFACE_AREA, rel=0.0, abs=1e-12), (
        "fallback should calculate the square area"
    )
    assert result.degenerate_faces == NO_DEGENERATE_FACES, "square faces are non-degenerate"
    assert result.watertight is None, "fallback does not compute watertightness"


def test_validation_fallback_counts_disconnected_components() -> None:
    """Count disconnected mesh islands separately."""
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (10.0, 0.0, 0.0),
        (11.0, 0.0, 0.0),
        (10.0, 1.0, 0.0),
    )
    triangles = ((0, 1, 2), (3, 4, 5))
    result = validate_mesh(vertices, triangles, prefer_trimesh=False)
    assert result.components == DISCONNECTED_COMPONENT_COUNT, (
        "two detached triangles are two components"
    )


def test_fallback_surface_area_uses_triangle_geometry() -> None:
    """Calculate the expected area for a 3-4-5 right triangle."""
    vertices = ((0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 4.0, 0.0))
    result = validate_mesh(vertices, ((0, 1, 2),), prefer_trimesh=False)
    assert result.surface_area == pytest.approx(RIGHT_TRIANGLE_SURFACE_AREA, rel=0.0, abs=1e-12), (
        "right-triangle area should equal half the base-height product"
    )


@given(
    width=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
    height=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_fallback_surface_area_obeys_base_height_identity(width: float, height: float) -> None:
    """Match the right-triangle base-height identity across generated inputs.

    Args:
        width: Positive length of the triangle base.
        height: Positive perpendicular height of the triangle.
    """
    vertices = ((0.0, 0.0, 0.0), (width, 0.0, 0.0), (0.0, height, 0.0))
    result = validate_mesh(vertices, ((0, 1, 2),), prefer_trimesh=False)
    assert result.surface_area == pytest.approx(width * height / 2.0, rel=1e-12, abs=1e-12), (
        "triangle area should follow the base-height identity"
    )


def test_degenerate_faces_include_distinct_collinear_vertices() -> None:
    """Report a zero-area triangle whose vertices are distinct and collinear."""
    vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0))
    result = validate_mesh(vertices, ((0, 1, 2),), prefer_trimesh=False)
    assert result.degenerate_faces == ONE_DEGENERATE_FACE, "collinear triangle should be degenerate"
    assert result.surface_area == pytest.approx(ZERO_SURFACE_AREA, rel=0.0, abs=1e-12), (
        "collinear triangle should have zero area"
    )


def test_validation_rejects_bad_indices() -> None:
    """Reject face indices that point outside the vertex collection."""
    with pytest.raises(ValueError, match="out of range"):
        validate_mesh(((0.0, 0.0, 0.0),) * 3, ((0, 1, 4),), prefer_trimesh=False)


def test_vertex_clearance_is_translation_sensitive() -> None:
    """Measure clearance from world-space positions rather than local offsets."""
    clearance = nearest_target_clearance(((0.0, 0.0, 2.0),), ((0.0, 0.0, 0.0),))
    assert clearance == pytest.approx(2.0, rel=0.0, abs=1e-9), (
        "two units of vertical translation should produce two units of clearance"
    )


def test_large_vertex_clearance_returns_exact_nearest_distance() -> None:
    """Preserve exact nearest-point distances when the spatial index is required."""
    garment = tuple((float(index), 5.0, 0.0) for index in range(48))
    target = tuple((float(index), 0.0, 0.0) for index in range(48))
    assert nearest_target_clearance(garment, target) == pytest.approx(5.0, rel=0.0, abs=1e-9), (
        "parallel point sequences should preserve their five-unit separation"
    )


def test_nearest_target_observation_returns_the_target_vertex_at_minimum_distance() -> None:
    """Return the nearest target coordinate together with its measured distance."""
    garment = ((2.0, 3.0, 4.0), (10.0, 10.0, 10.0))
    target = ((2.0, 0.0, 4.0), (10.0, 7.0, 10.0), (100.0, 100.0, 100.0))
    distance, point = nearest_target_observation(garment, target)
    assert distance == pytest.approx(3.0, rel=0.0, abs=1e-9), (
        "nearest target distance should be three units"
    )
    assert point == (2.0, 0.0, 4.0), "observation should return the closest target vertex"


def test_trimesh_surface_clearance_is_optional() -> None:
    """Use trimesh when present and recognize its explicit missing-dependency error."""
    vertices, triangles = square_mesh()
    try:
        distance = nearest_surface_clearance(((5.0, 5.0, 3.0),), vertices, triangles)
    except RuntimeError as exc:
        assert "trimesh" in str(exc).lower(), (
            "optional-surface failure should identify the trimesh dependency"
        )
    else:
        assert distance == pytest.approx(3.0, rel=0.0, abs=1e-9), (
            "point above the square should report its perpendicular distance"
        )


def test_degenerate_face_is_reported_without_trimesh() -> None:
    """Report a face with a repeated vertex without relying on trimesh."""
    result = validate_mesh(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 1),),
        prefer_trimesh=False,
    )
    assert result.degenerate_faces == ONE_DEGENERATE_FACE, "repeated-vertex face is degenerate"


@settings(max_examples=40, deadline=None)
@given(scale=st.floats(min_value=1e-4, max_value=1e4, allow_nan=False, allow_infinity=False))
def test_triangle_surface_area_scales_quadratically(scale: float) -> None:
    """Uniformly scaling a mesh by s multiplies triangle area by s squared.

    Args:
        scale: Positive uniform scale applied to every triangle vertex.
    """
    vertices = ((0.0, 0.0, 0.0), (3.0 * scale, 0.0, 0.0), (0.0, 4.0 * scale, 0.0))
    result = validate_mesh(vertices, ((0, 1, 2),))
    assert result.surface_area == pytest.approx(6.0 * scale * scale, rel=1e-10, abs=1e-14), (
        "triangle surface area should scale with the square of its linear scale"
    )


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    sys.stdout.write("mesh validation tests passed\n")

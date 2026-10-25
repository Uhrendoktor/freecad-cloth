# Copyright (C) 2026 FreeCAD Cloth contributors
"""Vectorized visual sanity checks for avatar mesh geometry."""

import pytest

from freecad_cloth.avatar.AvatarVisualSanity import AvatarVisualSanityError, inspect_avatar_mesh


def test_accepts_sane_humanoid_bounds() -> None:
    """Accept a mannequin with plausible width, depth, and Z-height."""
    vertices = ((-100, -50, 0), (100, 50, 1750), (-110, 45, 800), (110, -45, 800))
    triangles = ((0, 1, 2), (0, 2, 3))
    result = inspect_avatar_mesh(vertices, triangles, expected_height=1750)
    assert result.height == 1750.0
    assert result.triangle_count == 2
    assert result.lateral_height_ratio < 0.2


def test_accepts_sane_humanoid_even_when_depth_exceeds_width() -> None:
    """Measure horizontal dimensions independently from authoritative Z-height."""
    vertices = ((-150, -260, 0), (150, 260, 1750), (-120, 250, 900), (120, -250, 900))
    triangles = ((0, 1, 2), (0, 2, 3))
    result = inspect_avatar_mesh(vertices, triangles, expected_height=1750)
    assert result.height == 1750.0
    assert result.width == 520.0
    assert result.depth == 300.0


def test_rejects_empty_mesh() -> None:
    """Reject a mesh without vertices or faces."""
    with pytest.raises(AvatarVisualSanityError, match="empty"):
        inspect_avatar_mesh((), ())


def test_rejects_invalid_triangle_indices() -> None:
    """Reject triangles that refer to vertices outside the input array."""
    with pytest.raises(AvatarVisualSanityError, match="invalid triangle index"):
        inspect_avatar_mesh(((0, 0, 0), (1, 0, 0), (0, 1, 1)), ((0, 1, 3),))


def test_rejects_unrealistically_wide_avatar() -> None:
    """Reject excessive lateral extent for an otherwise plausible height."""
    vertices = ((-900, -100, 0), (900, 100, 1750), (-850, 50, 900), (850, -50, 900))
    triangles = ((0, 1, 2), (0, 2, 3))
    with pytest.raises(AvatarVisualSanityError, match="lateral span"):
        inspect_avatar_mesh(vertices, triangles, expected_height=1750)


def test_rejects_large_depth_without_treating_it_as_height() -> None:
    """Reject excessive depth without mistaking it for body height."""
    vertices = ((-100, -900, 0), (100, 900, 1750), (-110, 850, 900), (110, -850, 900))
    triangles = ((0, 1, 2), (0, 2, 3))
    with pytest.raises(AvatarVisualSanityError, match="lateral span"):
        inspect_avatar_mesh(vertices, triangles, expected_height=1750)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_vertex_coordinates(value: float) -> None:
    """Reject non-finite vertex coordinates before computing avatar bounds."""
    vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, value, 2.0))
    triangles = ((0, 1, 2),)
    with pytest.raises(AvatarVisualSanityError, match="finite"):
        inspect_avatar_mesh(vertices, triangles)


def test_rejects_wrong_height() -> None:
    """Reject a mannequin whose height differs from the expected measurement."""
    vertices = ((-100, -50, 0), (100, 50, 1700), (-110, 45, 800), (110, -45, 800))
    triangles = ((0, 1, 2), (0, 2, 3))
    with pytest.raises(AvatarVisualSanityError, match="differs from expected"):
        inspect_avatar_mesh(vertices, triangles, expected_height=1750)

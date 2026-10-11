"""Headless behavioral tests for the neutral collision-surface value object."""

import pytest

from freecad_cloth.shared.collision import CollisionSurface, surface_from_triangles


def _triangle_surface():
    return surface_from_triangles(
        ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        ((0, 1, 2),),
    )


def test_surface_from_triangles_normalizes_and_validates_values():
    surface = surface_from_triangles(
        ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        ((0, 1, 2),),
        region="avatar",
        thickness=2,
    )
    assert isinstance(surface, CollisionSurface)
    assert surface.vertices[1] == (1.0, 0.0, 0.0)
    assert surface.triangles == ((0, 1, 2),)
    assert surface.region == "avatar"
    assert surface.thickness == 2.0


def test_collision_surface_is_immutable_and_can_change_thickness():
    surface = _triangle_surface()
    with pytest.raises(AttributeError):
        surface.thickness = 1.0
    thicker = surface.with_thickness(3.0)
    assert thicker.vertices == surface.vertices
    assert thicker.triangles == surface.triangles
    assert thicker.region == surface.region
    assert thicker.thickness == 3.0


def test_collision_surface_rejects_invalid_geometry_and_thickness():
    with pytest.raises(ValueError, match="needs vertices and triangles"):
        surface_from_triangles((), ())
    with pytest.raises(ValueError, match="thickness"):
        surface_from_triangles(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            ((0, 1, 2),),
            thickness=-1,
        )
    with pytest.raises(ValueError, match="triangle index"):
        surface_from_triangles(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            ((0, 1, 9),),
        )
    with pytest.raises(ValueError, match="region"):
        surface_from_triangles(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            ((0, 1, 2),),
            region="   ",
        )


def test_collision_surface_center_is_deterministic():
    surface = _triangle_surface()
    assert surface.center == pytest.approx((1 / 3, 1 / 3, 0.0))

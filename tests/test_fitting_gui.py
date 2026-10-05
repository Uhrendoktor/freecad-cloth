"""Regression coverage for the direct-manipulation fitting frontend."""

from types import SimpleNamespace

from freecad_cloth.avatar.FittingGui import arrangement_rotation, nearest_arrangement_point


def test_nearest_arrangement_point_returns_closest_candidate_within_threshold():
    points = (
        SimpleNamespace(X=0.0, Y=0.0, RotationZ=0.0, WrapDirection="front"),
        SimpleNamespace(X=10.0, Y=0.0, RotationZ=15.0, WrapDirection="back"),
    )

    assert nearest_arrangement_point((8.0, 1.0), points, 3.0) is points[1]
    assert nearest_arrangement_point((20.0, 0.0), points, 3.0) is None


def test_nearest_arrangement_point_prefers_closest_even_when_input_is_unsorted():
    points = (
        SimpleNamespace(X=9.0, Y=9.0),
        SimpleNamespace(X=2.0, Y=2.0),
        SimpleNamespace(X=4.0, Y=4.0),
    )

    assert nearest_arrangement_point((3.0, 3.0), points, 5.0) is points[2]


def test_arrangement_rotation_maps_wrap_direction_to_viewport_rotation():
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="front")) == 5.0
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="back")) == 185.0
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="left")) == 95.0
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="right")) == -85.0

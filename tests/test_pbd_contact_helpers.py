"""Tests for the import-safe shared PBD diagnostic helpers."""

from types import SimpleNamespace

import pytest

from freecad_cloth.common import MeshValidation
from tests.support.pbd_contact_helpers import nearest_surface_distance


def test_surface_distance_fallback_uses_spatial_index(monkeypatch):
    """Missing exact point-to-triangle queries must not fall back to a quadratic Python loop."""

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("surface query backend unavailable")

    monkeypatch.setattr(MeshValidation, "nearest_surface_clearance", unavailable)
    vertices = tuple((float(index), 0.0, 0.0) for index in range(5000))
    garment_points = tuple((float(index), 0.0, 5.0) for index in range(5000))
    surface = SimpleNamespace(vertices=vertices, triangles=((0, 1, 2),))

    assert nearest_surface_distance(garment_points, surface) == pytest.approx(5.0)

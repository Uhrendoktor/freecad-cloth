from pathlib import Path

import numpy as np
import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.simulation.TissuContainment import build_authored_surface_index


def _cube_surface(reverse=False):
    vertices = (
        (-10, -10, -10), (10, -10, -10), (10, 10, -10), (-10, 10, -10),
        (-10, -10, 10), (10, -10, 10), (10, 10, 10), (-10, 10, 10),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (3, 2, 6), (3, 6, 7),
        (0, 3, 7), (0, 7, 4),
        (1, 5, 6), (1, 6, 2),
    )
    if reverse:
        triangles = tuple((a, c, b) for a, b, c in triangles)
    return surface_from_triangles(vertices, triangles)


def test_authored_containment_classifies_closed_mesh_by_parity():
    surface = _cube_surface()
    index = build_authored_surface_index(surface.vertices, surface.triangles)

    assert index.contains((0.0, 0.0, 0.0))
    assert not index.contains((25.0, 0.0, 0.0))
    assert not index.contains((10.0, 0.0, 0.0))


def test_authored_containment_uses_outward_authored_winding_for_projection():
    for reverse in (False, True):
        surface = _cube_surface(reverse=reverse)
        index = build_authored_surface_index(surface.vertices, surface.triangles)
        target = index.correction((9.0, 0.0, 0.0), 0.5)
        assert target is not None
        projected, penetration = target
        assert np.allclose(projected, (10.5, 0.0, 0.0))
        assert penetration == pytest.approx(1.5, abs=1e-12)
        assert index.correction((11.0, 0.0, 0.0), 0.5) is None


def test_authored_containment_rejects_non_manifold_mesh():
    surface = _cube_surface()
    with pytest.raises(ValueError, match="closed and consistently wound"):
        build_authored_surface_index(surface.vertices, surface.triangles[:-1])


def test_tissu_backend_uses_full_authored_surface_for_containment():
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "simulation" / "TissuBackend.py").read_text(encoding="utf-8")

    assert "_source_collision_surface" in source
    assert "_authored_containment_index = build_authored_surface_index" in source
    assert "CLOTH_TISSU_AUTHORED_CONTAINMENT" in source
    assert "particle.set_position" in source
    assert "particle.set_old_position" in source

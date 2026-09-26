from pathlib import Path
from types import SimpleNamespace

import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.simulation.TissuBackend import (
    _apply_authored_containment_correction,
    _tissu_authored_containment_enabled,
)
from freecad_cloth.simulation.TissuContainment import (
    AuthoredSurfaceContainment,
    get_authored_surface_containment,
)


def _cube_surface(thickness=2.0):
    vertices = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
        (10.0, 0.0, 10.0),
        (10.0, 10.0, 10.0),
        (0.0, 10.0, 10.0),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    return surface_from_triangles(vertices, triangles, region="cube", thickness=thickness)


def test_authored_surface_requires_closed_two_manifold():
    surface = surface_from_triangles(
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        ((0, 1, 2),),
        region="open",
        thickness=1.0,
    )
    with pytest.raises(ValueError, match="must be closed"):
        AuthoredSurfaceContainment(surface)


def test_parity_classifier_and_outward_winding_are_deterministic():
    surface = _cube_surface()
    containment = AuthoredSurfaceContainment(surface)

    assert containment.contains((5.0, 5.0, 5.0))
    assert not containment.contains((15.0, 5.0, 5.0))

    first = containment.nearest_surface_point((9.0, 5.0, 5.0))
    second = containment.nearest_surface_point((9.0, 5.0, 5.0))
    assert first == second
    closest, normal, distance_sq, triangle_index = first
    assert closest == (10.0, 5.0, 5.0)
    assert normal == (1.0, 0.0, 0.0)
    assert distance_sq == pytest.approx(1.0)
    assert triangle_index in {6, 7}


def test_inside_particle_is_corrected_to_authored_surface_plus_thickness():
    containment = AuthoredSurfaceContainment(_cube_surface(thickness=2.0))

    corrected = containment.correct((9.0, 5.0, 5.0))

    assert corrected == (12.0, 5.0, 5.0)
    assert not containment.contains(corrected)


def test_surface_acceleration_is_cached_without_mutating_authority():
    surface = _cube_surface()
    first = get_authored_surface_containment(surface)
    second = get_authored_surface_containment(surface)

    assert first is second
    assert first.surface is surface
    assert surface.thickness == 2.0


def test_tissu_correction_resets_verlet_old_position():
    class Particle:
        def __init__(self):
            self.position = (0.009, 0.005, 0.005)
            self.old_position = (0.010, 0.005, 0.005)

        def get_inverse_mass(self):
            return 1.0

        def get_position(self):
            return self.position

        def set_position(self, value):
            self.position = tuple(float(component) for component in value)

        def set_old_position(self, value):
            self.old_position = tuple(float(component) for component in value)

    particle = Particle()
    sim = SimpleNamespace(solver=SimpleNamespace(get_particles=lambda: [particle]))
    containment = AuthoredSurfaceContainment(_cube_surface(thickness=2.0))

    corrected_count = _apply_authored_containment_correction(sim, containment)

    assert corrected_count == 1
    assert particle.position == pytest.approx((0.012, 0.005, 0.005))
    assert particle.old_position == particle.position


def test_tissu_authored_containment_is_explicitly_opt_in(monkeypatch):
    monkeypatch.delenv("CLOTH_TISSU_AUTHORED_CONTAINMENT", raising=False)
    assert not _tissu_authored_containment_enabled()
    monkeypatch.setenv("CLOTH_TISSU_AUTHORED_CONTAINMENT", "1")
    assert _tissu_authored_containment_enabled()


def test_tissu_backend_keeps_explicit_environment_gate_and_old_position_reset():
    source = (Path(__file__).resolve().parents[1] / "freecad_cloth" / "simulation" / "TissuBackend.py").read_text(
        encoding="utf-8"
    )
    assert 'os.environ.get("CLOTH_TISSU_AUTHORED_CONTAINMENT", "0")' in source
    assert "self._source_collision_surface" in source
    assert "self._authored_containment = get_authored_surface_containment" in source
    assert "particle.set_old_position(corrected_position)" in source
    assert "CLOTH_TISSU_COLLISION_TRIANGLES" in source

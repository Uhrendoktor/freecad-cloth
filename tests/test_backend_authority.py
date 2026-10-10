from pathlib import Path

from freecad_cloth.shared.collision import surface_from_triangles
from freecad_cloth.simulation.PositionBasedDynamicsBackend import _pbd_collision_sdf_cache_key
from freecad_cloth.simulation.ClothBackend import (
    ClothSimulationBackend,
    validate_pinned_stitch_pairs,
)

ROOT = Path(__file__).resolve().parents[1]


def test_backend_boundary_is_small_and_solver_neutral():
    names = {
        name
        for name in ("step", "reset", "pin", "set_stitches", "positions", "finite")
        if hasattr(ClothSimulationBackend, name)
    }
    assert names == {"step", "reset", "pin", "set_stitches", "positions", "finite"}


def test_pbd_is_the_only_runtime_backend_implementation():
    backend_source = (ROOT / "freecad_cloth" / "simulation" / "ClothBackend.py").read_text(
        encoding="utf-8"
    )
    pbd_source = (
        ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py"
    ).read_text(encoding="utf-8")

    assert "default_backend_registry" not in backend_source
    assert "preferred_backend_name" not in backend_source
    assert "class XPBDBackend" not in backend_source
    assert "class PositionBasedDynamicsBackend" in pbd_source
    assert "class PositionBasedDynamicsBackend(ClothSimulationBackend)" in pbd_source


def test_pinned_pinned_stitch_rejects_nonzero_initial_separation():
    positions = ((0.0, 0.0, 0.0), (327.943695, 0.0, 0.0))
    records = (("TunicRightShoulder", "Front", "Back", ((0, 1),)),)

    try:
        validate_pinned_stitch_pairs(positions, (0, 1), records)
    except ValueError as exc:
        message = str(exc)
        assert "impossible pinned-pinned sewing constraint" in message
        assert "seam=TunicRightShoulder" in message
    else:
        raise AssertionError("physically impossible pinned-pinned stitch was accepted")


def test_pinned_pinned_stitch_allows_numerical_zero():
    positions = ((0.0, 0.0, 0.0), (1.0e-12, 0.0, 0.0))
    records = (("test-seam", "A", "B", ((0, 1),)),)

    validate_pinned_stitch_pairs(positions, (0, 1), records)


def test_simulation_workbench_does_not_force_a_backend_selector():
    source = (ROOT / "freecad_cloth" / "simulation" / "workbench.py").read_text(encoding="utf-8")

    assert "CLOTH_SIMULATION_BACKEND" not in source
    assert "preferred_backend_name" not in source


def test_pbd_collision_sdf_key_is_deterministic_and_covers_all_inputs():
    surface = surface_from_triangles(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=0.5,
    )
    key = _pbd_collision_sdf_cache_key(surface, [16, 16, 16])
    assert key == _pbd_collision_sdf_cache_key(surface, [16, 16, 16])
    assert key != _pbd_collision_sdf_cache_key(surface, [16, 16, 17])
    assert key != _pbd_collision_sdf_cache_key(surface.with_thickness(1.0), [16, 16, 16])

    moved = surface_from_triangles(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=0.5,
    )
    assert key != _pbd_collision_sdf_cache_key(moved, [16, 16, 16])

from pathlib import Path

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


def test_tissu_is_the_only_runtime_backend_implementation():
    backend_source = (ROOT / "freecad_cloth" / "simulation" / "ClothBackend.py").read_text(
        encoding="utf-8"
    )
    tissu_source = (ROOT / "freecad_cloth" / "simulation" / "TissuBackend.py").read_text(
        encoding="utf-8"
    )

    assert "default_backend_registry" not in backend_source
    assert "preferred_backend_name" not in backend_source
    assert "class XPBDBackend" not in backend_source
    assert "class TissuBackend" in tissu_source
    assert "class TissuBackend(ClothSimulationBackend)" in tissu_source


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

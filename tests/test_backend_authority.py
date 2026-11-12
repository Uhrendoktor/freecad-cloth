# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for the solver-neutral cloth backend boundary."""

from pathlib import Path

import pytest

from freecad_cloth.shared.Collision import surface_from_triangles
from freecad_cloth.simulation.cloth_backend import (
    ClothSimulationBackend,
    validate_pinned_stitch_pairs,
)

from freecad_cloth.simulation.PositionBasedDynamicsBackend import _pbd_collision_sdf_cache_key

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BACKEND_METHODS = {
    "step",
    "reset",
    "pin",
    "set_stitches",
    "positions",
    "finite",
}
PINNED_STITCH_GAP_MM = 327.943695
NUMERIC_ZERO_GAP_MM = 1.0e-12
SURFACE_THICKNESS_MM = 0.5
CHANGED_SURFACE_THICKNESS_MM = 1.0
GRID_RESOLUTION = (16, 16, 16)
CHANGED_GRID_RESOLUTION = (16, 16, 17)


def test_backend_boundary_is_small_and_solver_neutral() -> None:
    """Expose the core simulation operations without runtime-specific backend selection."""
    backend_methods = {
        name for name in EXPECTED_BACKEND_METHODS if hasattr(ClothSimulationBackend, name)
    }
    assert backend_methods == EXPECTED_BACKEND_METHODS, (
        "The simulation boundary must expose the six solver-neutral operations."
    )


def test_pbd_is_the_only_runtime_backend_implementation() -> None:
    """Keep the interface independent from the sole production PBD implementation."""
    backend_source = (ROOT / "freecad_cloth" / "simulation" / "cloth_backend.py").read_text(
        encoding="utf-8"
    )
    pbd_source = (
        ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py"
    ).read_text(encoding="utf-8")
    assert "default_backend_registry" not in backend_source, (
        "The backend interface must not contain a runtime backend registry."
    )
    assert "preferred_backend_name" not in backend_source, (
        "The backend interface must not select a preferred implementation."
    )
    assert "class XPBDBackend" not in backend_source, (
        "The interface module must not define a second runtime solver."
    )
    assert "class PositionBasedDynamicsBackend" in pbd_source, (
        "The PBD adapter must remain the concrete runtime implementation."
    )
    assert "class PositionBasedDynamicsBackend(ClothSimulationBackend)" in pbd_source, (
        "The PBD adapter must implement the shared backend boundary."
    )


def test_pinned_stitch_rejects_nonzero_initial_separation() -> None:
    """Reject two already-pinned particles joined by a physically impossible stitch."""
    positions = ((0.0, 0.0, 0.0), (PINNED_STITCH_GAP_MM, 0.0, 0.0))
    seam_records = (("TunicRightShoulder", "Front", "Back", ((0, 1),)),)
    with pytest.raises(ValueError, match="impossible pinned-pinned sewing constraint") as exc:
        validate_pinned_stitch_pairs(positions, (0, 1), seam_records)
    assert "seam=TunicRightShoulder" in str(exc.value), (
        "The validation error must identify the seam that violates the pin contract."
    )


def test_pinned_stitch_allows_numerical_zero_separation() -> None:
    """Allow a pinned pair whose separation is below the numerical tolerance."""
    positions = ((0.0, 0.0, 0.0), (NUMERIC_ZERO_GAP_MM, 0.0, 0.0))
    seam_records = (("test-seam", "A", "B", ((0, 1),)),)
    validate_pinned_stitch_pairs(positions, (0, 1), seam_records)


def test_simulation_workbench_does_not_force_a_backend_selector() -> None:
    """Keep runtime solver choice out of the workbench registration boundary."""
    source = (ROOT / "freecad_cloth" / "simulation" / "workbench.py").read_text(encoding="utf-8")
    assert "CLOTH_SIMULATION_BACKEND" not in source, (
        "The simulation workbench must not inject a backend environment selector."
    )
    assert "preferred_backend_name" not in source, (
        "The simulation workbench must not choose a preferred backend name."
    )


def test_pbd_collision_sdf_key_is_deterministic_and_covers_all_inputs() -> None:
    """Include surface geometry, thickness, and grid resolution in the SDF cache identity."""
    surface = surface_from_triangles(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=SURFACE_THICKNESS_MM,
    )
    key = _pbd_collision_sdf_cache_key(surface, list(GRID_RESOLUTION))
    assert key == _pbd_collision_sdf_cache_key(surface, list(GRID_RESOLUTION)), (
        "Identical SDF inputs must produce a deterministic cache key."
    )
    assert key != _pbd_collision_sdf_cache_key(surface, list(CHANGED_GRID_RESOLUTION)), (
        "Grid resolution changes must invalidate the SDF cache key."
    )
    thicker_surface = surface.with_thickness(CHANGED_SURFACE_THICKNESS_MM)
    assert key != _pbd_collision_sdf_cache_key(thicker_surface, list(GRID_RESOLUTION)), (
        "Collision thickness changes must invalidate the SDF cache key."
    )
    moved_surface = surface_from_triangles(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=SURFACE_THICKNESS_MM,
    )
    assert key != _pbd_collision_sdf_cache_key(moved_surface, list(GRID_RESOLUTION)), (
        "Surface geometry changes must invalidate the SDF cache key."
    )

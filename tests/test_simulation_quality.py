import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset, solver_parameters
from SimulationQualityRuntimeV2 import quality_discretization
from SimulationMeshQuality import quality_piece_mesh


def test_quality_presets_are_monotonic_and_distinct():
    assert set(QUALITY_PRESETS) == {"Fast", "Balanced", "Final"}
    assert preset("Fast").particle_distance > preset("Balanced").particle_distance > preset("Final").particle_distance
    assert preset("Fast").solver_iterations < preset("Final").solver_iterations


def test_material_defaults_and_solver_parameters():
    material = FabricMaterial()
    params = solver_parameters(preset("Final"), material)
    assert params["particle_distance"] == 2.0
    assert params["iterations"] == 16
    assert params["substeps"] == 2
    assert params["density_g_m2"] == 150.0
    assert params["thickness_mm"] == 0.5


@pytest.mark.parametrize("field,value", [("density_g_m2", 0), ("thickness_mm", 0), ("stretch", 1.1), ("shear", -0.1), ("bend", 2), ("friction", -1)])
def test_material_validation_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        FabricMaterial(**{field: value}).validate()


def test_unknown_quality_rejected():
    with pytest.raises(ValueError):
        preset("Ultra")


def test_pattern_mesh_density_changes_with_particle_distance():
    piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
    piece_obj = type("Piece", (), {
        "SewingOutline": repr(piece.outline),
        "DraftingBoundary": repr(piece.outline),
        "PieceId": piece.id,
        "Placement": None,
    })()
    coarse = quality_piece_mesh(piece_obj, 100.0, 20.0)
    fine = quality_piece_mesh(piece_obj, 100.0, 5.0)
    assert len(fine[0]) > len(coarse[0])

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from SimulationQuality import preset
from SimulationQualityRuntimeV2 import quality_discretization
from SimulationMeshQuality import quality_piece_mesh


def test_quality_presets_are_ordered_by_resolution():
    assert preset("Fast").particle_distance > preset("Balanced").particle_distance > preset("Final").particle_distance


def test_quality_discretization_increases_with_smaller_particle_distance():
    coarse = quality_discretization(4, 320.0, preset("Fast").particle_distance)
    fine = quality_discretization(4, 320.0, preset("Final").particle_distance)
    assert fine > coarse


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


if __name__ == "__main__":
    test_quality_presets_are_ordered_by_resolution()
    test_quality_discretization_increases_with_smaller_particle_distance()
    test_pattern_mesh_density_changes_with_particle_distance()
    print("simulation quality tests passed")

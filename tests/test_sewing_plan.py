import pytest

from PatternModel import PatternPiece, Seam
from SewingPlan import connected_components, validate_sewing_plan


def pieces():
    return [
        PatternPiece("Front", [(0, 0), (10, 0), (10, 5), (0, 5)], id="front"),
        PatternPiece("Back", [(0, 0), (10, 0), (10, 5), (0, 5)], id="back"),
        PatternPiece("Sleeve", [(0, 0), (5, 0), (5, 8), (0, 8)], id="sleeve"),
    ]


def test_valid_plan_reports_counts():
    seams = [Seam("front", 1, "back", 3, id="side")]
    assert validate_sewing_plan(pieces(), seams) == {"piece_count": 3, "seam_count": 1}


def test_unknown_piece_is_rejected():
    with pytest.raises(ValueError, match="unknown piece"):
        validate_sewing_plan(pieces(), [Seam("front", 1, "missing", 0, id="bad")])


def test_edge_index_is_checked_against_outline():
    with pytest.raises(ValueError, match="out of range"):
        validate_sewing_plan(pieces(), [Seam("front", 4, "back", 0, id="bad")])


def test_duplicate_seam_ids_are_rejected():
    seams = [Seam("front", 1, "back", 3, id="side"), Seam("front", 2, "back", 2, id="side")]
    with pytest.raises(ValueError, match="duplicate seam id"):
        validate_sewing_plan(pieces(), seams)


def test_components_include_unsewn_pieces():
    seams = [Seam("front", 1, "back", 3, id="side")]
    assert connected_components(pieces(), seams) == (("front", "back"), ("sleeve",))

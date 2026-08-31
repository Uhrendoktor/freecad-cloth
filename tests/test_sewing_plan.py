from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.sewing.SewingPlan import connected_components, validate_sewing_plan


def pieces():
    return [
        PatternPiece("Front", [(0, 0), (10, 0), (10, 5), (0, 5)], id="front"),
        PatternPiece("Back", [(0, 0), (10, 0), (10, 5), (0, 5)], id="back"),
        PatternPiece("Sleeve", [(0, 0), (5, 0), (5, 8), (0, 8)], id="sleeve"),
    ]


def assert_raises(exc_type, message, fn):
    try:
        fn()
    except exc_type as exc:
        assert message in str(exc)
        return
    raise AssertionError(f"expected {exc_type.__name__}")


def test_valid_plan_reports_counts():
    seams = [Seam("front", 1, "back", 3, id="side")]
    assert validate_sewing_plan(pieces(), seams) == {"piece_count": 3, "seam_count": 1}


def test_unknown_piece_is_rejected():
    assert_raises(ValueError, "unknown piece", lambda: validate_sewing_plan(pieces(), [Seam("front", 1, "missing", 0, id="bad")]))


def test_edge_index_is_checked_against_outline():
    assert_raises(ValueError, "out of range", lambda: validate_sewing_plan(pieces(), [Seam("front", 4, "back", 0, id="bad")]))


def test_duplicate_seam_ids_are_rejected():
    seams = [Seam("front", 1, "back", 3, id="side"), Seam("front", 2, "back", 2, id="side")]
    assert_raises(ValueError, "duplicate seam id", lambda: validate_sewing_plan(pieces(), seams))


def test_components_include_unsewn_pieces():
    seams = [Seam("front", 1, "back", 3, id="side")]
    assert connected_components(pieces(), seams) == (("front", "back"), ("sleeve",))


def run():
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("sewing plan tests passed")


if __name__ == "__main__":
    run()

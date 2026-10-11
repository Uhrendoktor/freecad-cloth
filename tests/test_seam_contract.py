from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.sewing.SeamGraph import SeamGraph


def graph():
    value = SeamGraph()
    value.add_piece(PatternPiece("A", [(0, 0), (10, 0), (10, 10)], id="a"))
    value.add_piece(PatternPiece("B", [(0, 0), (10, 0), (10, 10)], id="b"))
    return value


def test_graph_stores_canonical_seam():
    value = graph()
    seam = Seam("a", 0, "b", 1, id="s1", reversed_b=True)
    value.add_seam(seam)
    pair = value.seams["s1"]
    assert pair.seam is seam
    assert pair.id == "s1"
    assert pair.reversed_b is True


def test_graph_validation_rechecks_authoritative_seam():
    value = graph()
    value.add_seam(Seam("a", 0, "b", 1, id="s1"))
    value.validate()


def test_graph_rejects_unknown_piece_and_edge():
    value = graph()
    try:
        value.add_seam(Seam("a", 0, "missing", 0, id="bad"))
        raise AssertionError("unknown piece should be rejected")
    except ValueError as exc:
        assert "unknown pattern piece" in str(exc)

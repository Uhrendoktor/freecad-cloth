import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece, Seam
from SeamGraph import SeamGraph, Transform3D
from SewingAssembly import SewingAssembly, align_piece_to_seam, make_translation


def graph():
    a = PatternPiece("A", [(0, 0), (10, 0), (10, 5)], id="a")
    b = PatternPiece("B", [(0, 0), (10, 0), (10, 5)], id="b")
    g = SeamGraph()
    g.add_piece(a)
    g.add_piece(b)
    g.add_seam(Seam("a", 0, "b", 0, id="s1"), stitch_group="waist")
    return g


def test_pair_and_metadata_are_deterministic():
    a = SewingAssembly(graph())
    p = a.add_pair("s1")
    assert p.stitch_group == "waist"
    assert a.to_metadata() == {
        "pairs": (("s1", "waist", "endpoints", False),),
        "assembly": (("a", Transform3D.identity().matrix), ("b", Transform3D.identity().matrix)),
    }


def test_pair_rejects_duplicate_and_unknown_seam():
    a = SewingAssembly(graph())
    a.add_pair("s1")
    try:
        a.add_pair("s1")
        assert False
    except ValueError as exc:
        assert "already paired" in str(exc)
    try:
        a.add_pair("missing")
        assert False
    except ValueError as exc:
        assert "unknown seam" in str(exc)


def test_alignment_transform_persists_on_second_piece():
    g = graph()
    align_piece_to_seam(g, "s1", make_translation(12, 3, 0))
    assert g.assembly_transforms["b"].apply((1, 2, 0)) == (13, 5, 0)


def test_transform_rejects_wrong_shape():
    try:
        Transform3D(tuple(range(15)))
        assert False
    except ValueError as exc:
        assert "16 values" in str(exc)


if __name__ == "__main__":
    test_pair_and_metadata_are_deterministic()
    test_pair_rejects_duplicate_and_unknown_seam()
    test_alignment_transform_persists_on_second_piece()
    test_transform_rejects_wrong_shape()
    print("sewing assembly tests passed")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from SeamGraph import SeamGraph
from freecad_cloth.sewing.SewingAssembly import SewingPair
from freecad_cloth.sewing.SewingSemantics import SeamConstraint


def graph():
    value = SeamGraph()
    value.add_piece(PatternPiece("A", [(0, 0), (10, 0), (10, 10)], id="a"))
    value.add_piece(PatternPiece("B", [(0, 0), (10, 0), (10, 10)], id="b"))
    return value


def test_legacy_seam_constraint_wraps_canonical_seam():
    adapter = SeamConstraint("s1", "a", "0", "b", 1, reversed_b=True)
    assert adapter.seam == Seam("a", 0, "b", 1, id="s1", reversed_b=True)
    assert adapter.id == adapter.seam.id
    assert adapter.piece_a == adapter.seam.piece_a
    assert adapter.edge_b == adapter.seam.edge_b


def test_graph_stores_same_canonical_seam_instance():
    value = graph()
    seam = Seam("a", 0, "b", 1, id="s1", reversed_b=True)
    value.add_seam(seam)
    assert value.seams["s1"].seam is seam
    assert value.seams["s1"].reversed_b is True


def test_legacy_adapter_can_be_added_without_forking_seam_state():
    value = graph()
    adapter = SeamConstraint("s1", "a", 0, "b", 1, reversed_b=True)
    value.add_seam(adapter)
    assert value.seams["s1"].seam is adapter.seam


def test_sewing_pair_binds_and_derives_reversal_from_canonical_seam():
    value = graph()
    seam = Seam("a", 0, "b", 1, id="s1", reversed_b=True)
    value.add_seam(seam)
    pair = SewingPair("s1", "waist", reversed_b=False)
    pair.validate(value)
    assert pair.reversed_b is True


def test_non_numeric_legacy_edge_identifier_is_rejected_at_adapter_boundary():
    with pytest.raises(ValueError, match="integer outline indices"):
        SeamConstraint("bad", "a", "left-edge", "b", 0)

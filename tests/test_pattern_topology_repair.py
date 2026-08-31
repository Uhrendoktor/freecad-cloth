from types import SimpleNamespace

import pytest

from PatternTopologyRepair import (
    InvalidRepairTarget,
    TopologyRepairError,
    build_repair_plan,
    current_edge_candidates,
    seam_reference_status,
)
from SeamReference import capture_edge_reference


def _piece(piece_id="front", points=((0, 0), (10, 0), (10, 10), (0, 10))):
    return SimpleNamespace(PieceId=piece_id, SewingOutline=repr(points))


def _seam(piece_a, edge_a=0, piece_b=None, edge_b=0):
    piece_b = piece_b or _piece("back")
    records_a = current_edge_candidates(SimpleNamespace(PatternA=piece_a, PatternB=piece_b), "A")
    records_b = current_edge_candidates(SimpleNamespace(PatternA=piece_a, PatternB=piece_b), "B")
    ref_a = capture_edge_reference(piece_a.PieceId, records_a[edge_a]["id"], records_a[edge_a]["points"])
    ref_b = capture_edge_reference(piece_b.PieceId, records_b[edge_b]["id"], records_b[edge_b]["points"])
    return SimpleNamespace(
        SeamId="front-seam", Label="front seam", PatternA=piece_a, PatternB=piece_b,
        EdgeAId=ref_a.edge_id, EdgeASignature=ref_a.signature,
        EdgeBId=ref_b.edge_id, EdgeBSignature=ref_b.signature,
    )


def test_changed_reference_is_reported_before_repair():
    original = _piece()
    seam = _seam(original)
    seam.PatternA = _piece(points=((0, 0), (12, 0), (10, 10), (0, 10)))
    assert seam_reference_status(seam, "A") == (False, "changed")


def test_missing_reference_can_be_explicitly_mapped_to_current_edge():
    piece = _piece(); seam = _seam(piece)
    seam.EdgeAId = "front:edge:99"; seam.EdgeASignature = "missing"
    target = current_edge_candidates(seam, "A")[2]["id"]
    plan = build_repair_plan([(seam, "A", target)])
    assert len(plan) == 1 and plan[0][2]["id"] == target


def test_repair_target_must_be_a_current_semantic_edge():
    seam = _seam(_piece())
    with pytest.raises(InvalidRepairTarget):
        build_repair_plan([(seam, "A", "front:edge:404")])


def test_duplicate_side_mapping_is_rejected_before_mutation():
    seam = _seam(_piece()); edge = current_edge_candidates(seam, "A")[1]["id"]
    with pytest.raises(TopologyRepairError, match="duplicate repair target"):
        build_repair_plan([(seam, "A", edge), (seam, "A", edge)])

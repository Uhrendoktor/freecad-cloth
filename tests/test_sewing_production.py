import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingCorrespondence import analyze_correspondence
from SewingNetwork import SewingMember, build_mn_seams
from SewingValidation import seam_diagnostic, validate_sewing_graph


def _doc(*objects):
    return SimpleNamespace(Objects=list(objects))


def _piece(pid):
    return SimpleNamespace(PatternType="PatternPiece", PieceId=pid)


def _seam(sid, a, b, status="Valid", la=100.0, lb=100.0, reversed_b=False):
    return SimpleNamespace(SeamId=sid, PieceA=a, PieceB=b, EdgeA=0, EdgeB=0,
                           EdgeAId="", EdgeBId="", Status=status, LengthA=la,
                           LengthB=lb, LengthDifference=abs(la-lb), ReversedB=reversed_b,
                           StartA=0.0, EndA=1.0, StartB=0.0, EndB=1.0)


def test_valid_seam_and_reversed_seam_diagnostics():
    valid = _seam("s1", "A", "B")
    reversed_seam = _seam("s2", "A", "B", reversed_b=True)
    assert seam_diagnostic(valid)["status"] == "Valid"
    assert seam_diagnostic(reversed_seam)["reversed"] is True
    report = analyze_correspondence(100, 100, reversed_b=True)
    assert report.valid and report.status == "reversed"


def test_mismatched_lengths_are_explicitly_invalid_for_acceptance():
    report = analyze_correspondence(100, 112, length_tolerance=0.05)
    assert report.status == "length_mismatch"
    assert not report.valid


def test_one_to_many_and_many_to_many_partition_deterministically():
    one_to_many = build_mn_seams("1n", [SewingMember("A", 0)], [SewingMember("B", 0), SewingMember("B", 1)],
                                  {("A", 0): 100, ("B", 0): 40, ("B", 1): 60})
    many_to_many = build_mn_seams("mn", [SewingMember("A", 0), SewingMember("A", 1)],
                                  [SewingMember("B", 0), SewingMember("B", 1)],
                                  {("A", 0): 60, ("A", 1): 40, ("B", 0): 30, ("B", 1): 70})
    assert len(one_to_many) == 2
    assert len(many_to_many) == 3
    assert all(s.stitch_group == "mn" for s in many_to_many)


def test_complete_graph_reports_isolated_and_invalid_nodes():
    a, b, c = _piece("A"), _piece("B"), _piece("C")
    complete = _doc(a, b, c, _seam("s1", "A", "B"), _seam("s2", "B", "C"))
    assert validate_sewing_graph(complete)["status"] == "Valid"
    incomplete = _doc(a, b, c, _seam("s1", "A", "B"))
    report = validate_sewing_graph(incomplete)
    assert report["status"] == "Incomplete" and report["isolated"] == ("C",)
    invalid = _doc(a, b, _seam("broken", "A", "B", "Changed reference"))
    assert validate_sewing_graph(invalid)["status"] == "Invalid"


def test_network_graph_member_counts_are_inspectable():
    a, b = _piece("A"), _piece("B")
    members = (_seam("mn-1", "A", "B"), _seam("mn-2", "A", "B"))
    network = SimpleNamespace(SewingType="SewingNetwork", RelationshipId="rel", Seams=members,
                              Status="Valid", LengthDifference=0.0, InvalidReason="", Name="Network")
    report = validate_sewing_graph(_doc(a, b, *members, network))
    assert report["network_count"] == 1
    assert report["networks"][0]["segments"] == 2

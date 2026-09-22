import math
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.PatternObjects import (
    add_pattern_piece,
    add_seam,
    refresh_edge_reference_signature,
)
from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece
from freecad_cloth.sewing.SeamGraph import SeamGraph
from freecad_cloth.sewing.SewingCorrespondence import (
    STATUS_LENGTH_MISMATCH,
    STATUS_REVERSED,
    analyze_correspondence,
)
from freecad_cloth.sewing.SewingNetwork import (
    SewingMember,
    SewingNetworkProxy,
    build_mn_seams,
)
from freecad_cloth.sewing.SewingView import seam_visual_markers

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None


def _set_native_boundary(sketch, piece_id, arc):
    sketch.clear()
    sketch.addGeometry(
        [
            Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)),
            arc,
            Part.LineSegment(App.Vector(10, 10, 0), App.Vector(0, 10, 0)),
            Part.LineSegment(App.Vector(0, 10, 0), App.Vector(0, 0, 0)),
        ],
        False,
    )
    sketch.SemanticEdgeIds = [
        f"{piece_id}:edge:0",
        f"{piece_id}:edge:1",
        f"{piece_id}:edge:2",
        f"{piece_id}:edge:3",
    ]
    sketch.GeometryAuthority = "Sketcher"


def test_correspondence_evidence_is_machine_checkable_and_directional():
    mismatch = analyze_correspondence(100.0, 120.0, length_tolerance=0.05)
    assert mismatch.status == STATUS_LENGTH_MISMATCH
    assert mismatch.severity == "error"
    assert mismatch.evidence()["recovery"] == (
        "edit the pattern geometry or seam ranges; do not hide the mismatch with tolerance"
    )

    reversed_report = analyze_correspondence(100.0, 100.0, reversed_b=True)
    assert reversed_report.status == STATUS_REVERSED
    assert reversed_report.severity == "info"
    assert reversed_report.evidence()["reversed_b"] is True


def test_true_mn_physical_breakpoints_are_proportional_and_reversed():
    lengths = {
        ("A", 0): 150.0,
        ("A", 1): 100.0,
        ("B", 0): 100.0,
        ("B", 1): 150.0,
    }
    seams = build_mn_seams(
        "mn-22",
        [SewingMember("A", 0), SewingMember("A", 1)],
        [SewingMember("B", 0), SewingMember("B", 1)],
        lengths,
        reversed_b=True,
        alignment="uniform",
    )
    assert len(seams) == 3
    assert [
        (round(s.start_a, 8), round(s.end_a, 8), round(s.start_b, 8), round(s.end_b, 8))
        for s in seams
    ] == [
        (0.0, round(2 / 3, 8), 0.0, 1.0),
        (round(2 / 3, 8), 1.0, 0.0, round(1 / 3, 8)),
        (0.0, 1.0, round(1 / 3, 8), 1.0),
    ]
    assert all(s.reversed_b for s in seams)


def test_seam_graph_uses_physical_arc_length_over_nonuniform_sampling():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("A", [(0, 0), (10, 0), (10, 10), (0, 10)], id="A"))
    graph.add_piece(PatternPiece("B", [(0, 0), (10, 0), (10, 10), (0, 10)], id="B"))
    graph.add_seam(
        Seam(
            "A", 1, "B", 3, id="m1",
            start_a=0.0, end_a=0.4, stitch_group="mn",
        )
    )
    graph.add_seam(
        Seam(
            "A", 1, "B", 2, id="m2",
            start_a=0.4, end_a=1.0, stitch_group="mn",
        )
    )
    edges = {
        ("A", 1): (10, 11, 12, 13, 14, 15),
        ("B", 3): (20, 21, 22, 23),
        ("B", 2): (30, 31, 32, 33),
    }
    points = {
        ("A", 1): ((0.0, 0.0), (0.1, 0.0), (0.4, 0.0), (1.2, 0.0), (4.0, 0.0), (10.0, 0.0)),
        ("B", 3): ((0.0, 0.0), (2.0, 0.0), (5.0, 0.0), (10.0, 0.0)),
        ("B", 2): ((0.0, 0.0), (1.0, 0.0), (4.0, 0.0), (10.0, 0.0)),
    }
    assert graph.stitch_pairs(edges, edge_points=points) == (
        (10, 20), (12, 21), (13, 22), (14, 23),
        (12, 30), (13, 31), (14, 32), (15, 33),
    )


def test_reversed_seam_graph_mapping_is_explicit():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("A", [(0, 0), (10, 0), (10, 10), (0, 10)], id="A"))
    graph.add_piece(PatternPiece("B", [(0, 0), (10, 0), (10, 10), (0, 10)], id="B"))
    graph.add_seam(Seam("A", 1, "B", 3, id="reverse", reversed_b=True, stitch_group="reverse"))
    edges = {("A", 1): (10, 11, 12, 13), ("B", 3): (20, 21, 22, 23)}
    points = {
        ("A", 1): ((0.0, 0.0), (1.0, 0.0), (3.0, 0.0), (10.0, 0.0)),
        ("B", 3): ((0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (12.0, 0.0)),
    }
    assert graph.stitch_pairs(edges, edge_points=points) == ((10, 23), (12, 22), (13, 20))


def test_network_proxy_exposes_shared_mismatch_recovery():
    module = __import__("freecad_cloth.sewing.SewingNetwork", fromlist=["_network_lengths"])
    old_lengths = module._network_lengths
    seam = SimpleNamespace(
        SeamId="mn-1-1",
        Status="Valid",
        StitchGroup="mn-1",
        Document=SimpleNamespace(Objects=()),
        PieceA="A",
        PieceB="B",
    )
    network = SimpleNamespace(
        Seams=(seam,),
        RelationshipId="mn-1",
        Status="Valid",
        InvalidReason="",
        SegmentCount=1,
        LengthA=0.0,
        LengthB=0.0,
        LengthDifference=0.0,
        RelativeTolerance=0.05,
        CorrespondenceStatus="valid",
        CorrespondenceMessage="seam correspondence is valid",
        CorrespondenceRecovery="no repair required",
        CorrespondenceSeverity="info",
    )
    module._network_lengths = lambda seams: (100.0, 120.0)
    try:
        SewingNetworkProxy().execute(network)
    finally:
        module._network_lengths = old_lengths
    assert network.CorrespondenceStatus == "length_mismatch"
    assert network.CorrespondenceSeverity == "error"
    assert network.CorrespondenceRecovery == (
        "edit the pattern geometry or seam ranges; do not hide the mismatch with tolerance"
    )


def test_direction_notch_and_correspondence_visual_contract_is_explicit():
    a = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    b = ((20.0, 10.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0))
    markers = seam_visual_markers(a, b)
    assert markers["correspondence"][0][1] == b[0]
    assert markers["correspondence"][-1][1] == b[-1]
    assert markers["direction_A"][1] == (1.0, 0.0)
    assert markers["direction_B"][1] == (-1.0, 0.0)
    assert markers["notch_B"][1] == (0.0, -1.0)


def test_native_mn_save_reload_topology_edit_invalidates_without_retargeting():
    if App is None or Part is None:
        return
    document = App.newDocument("Sewing845NativeMN")
    path = None
    try:
        piece_a = PatternPiece("A", [(0, 0), (10, 0), (10, 10), (0, 10)], id="native-mn-a")
        piece_b = PatternPiece("B", [(0, 0), (10, 0), (10, 10), (0, 10)], id="native-mn-b")
        obj_a = add_pattern_piece(document, piece_a)
        obj_b = add_pattern_piece(document, piece_b)
        sketch_a = create_sketch_for_piece(piece_a, document)
        create_sketch_for_piece(piece_b, document)
        _set_native_boundary(
            sketch_a,
            "native-mn-a",
            Part.ArcOfCircle(
                Part.Circle(App.Vector(10, 5, 0), App.Vector(0, 0, 1), 5),
                -math.pi / 2,
                math.pi / 2,
            ),
        )
        document.recompute()

        models = build_mn_seams(
            "native-mn",
            [SewingMember(obj_a.PieceId, 0), SewingMember(obj_a.PieceId, 1)],
            [SewingMember(obj_b.PieceId, 0), SewingMember(obj_b.PieceId, 1)],
            {
                (obj_a.PieceId, 0): 10.0,
                (obj_a.PieceId, 1): 10.0,
                (obj_b.PieceId, 0): 10.0,
                (obj_b.PieceId, 1): 10.0,
            },
        )
        seams = [add_seam(document, model) for model in models]
        network = __import__(
            "freecad_cloth.sewing.SewingNetwork",
            fromlist=["add_sewing_network"],
        ).add_sewing_network(document, seams, "native-mn", "NativeMNNetwork")
        document.recompute()
        assert len(network.Seams) == 2
        assert str(network.Status) == "Valid"

        fd, path = tempfile.mkstemp(suffix=".FCStd")
        os.close(fd)
        document.saveAs(path)
        App.closeDocument(document.Name)
        document = None

        reloaded = App.openDocument(path)
        reloaded.recompute()
        network = next(
            obj for obj in reloaded.Objects
            if str(getattr(obj, "RelationshipId", "")) == "native-mn"
        )
        restored_a = next(
            obj for obj in reloaded.Objects
            if str(getattr(obj, "PieceId", "")) == "native-mn-a"
        )
        sketch = restored_a.Sketch
        _set_native_boundary(
            sketch,
            "native-mn-a",
            Part.ArcOfCircle(
                Part.Circle(App.Vector(5, 5, 0), App.Vector(0, 0, 1), math.sqrt(50)),
                -math.pi / 4,
                math.pi / 4,
            ),
        )
        reloaded.recompute()

        changed = [seam for seam in network.Seams if str(seam.Status) == "Changed reference"]
        valid = [seam for seam in network.Seams if str(seam.Status) == "Valid"]
        assert len(changed) == 1
        assert len(valid) == 1
        assert str(network.Status) == "Invalid"

        changed_seam = changed[0]
        before_id = str(changed_seam.EdgeAId)
        changed_seam.EdgeASignature = refresh_edge_reference_signature(
            changed_seam.PatternA,
            changed_seam.EdgeAId,
        )
        reloaded.recompute()
        assert before_id == str(changed_seam.EdgeAId)
        assert all(str(seam.Status) == "Valid" for seam in network.Seams)
        assert str(network.Status) == "Valid"
        App.closeDocument(reloaded.Name)
    finally:
        try:
            if path:
                os.unlink(path)
        except OSError:
            pass
        if document is not None and document.Name in App.listDocuments():
            App.closeDocument(document.Name)

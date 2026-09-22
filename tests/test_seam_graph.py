import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.sewing.SeamGraph import SeamGraph, Transform3D


def piece(name, ident): return PatternPiece(name, [(0, 0), (10, 0), (10, 10), (0, 10)], id=ident)


def graph():
    value = SeamGraph(); value.add_piece(piece("left", "left")); value.add_piece(piece("right", "right"))
    value.add_seam(Seam("left", 1, "right", 3, id="side", stitch_group="waist"))
    return value


def test_seam_graph_validates_references_and_keeps_metadata_stable():
    value = graph(); first = value.to_metadata(); second = value.to_metadata()
    assert first == second; assert first["seams"][0][:3] == ("side", "waist", "endpoints")


def test_seam_semantics_are_canonical():
    seam = Seam("left", 1, "right", 3, id="side", alignment="uniform", stitch_group="waist", kind="hem")
    value = SeamGraph(); value.add_piece(piece("left", "left")); value.add_piece(piece("right", "right")); value.add_seam(seam)
    pair = value.seams["side"]
    assert pair.seam is seam
    assert pair.alignment == "uniform"
    assert pair.stitch_group == "waist"
    assert value.to_metadata()["seams"][0][-1] == "hem"


def test_reversed_normalized_ranges_generate_deterministic_stitches():
    value = graph(); edges = {("left", 1): (10, 11, 12, 13, 14), ("right", 3): (20, 21, 22, 23, 24)}
    assert value.stitch_pairs(edges) == ((10, 20), (12, 22), (14, 24))
    value.seams["side"] = value.seams["side"].__class__(Seam("left", 1, "right", 3, id="side", reversed_b=True, stitch_group="waist"), "waist", "endpoints")
    assert value.stitch_pairs(edges) == ((10, 24), (12, 22), (14, 20))


def test_assembly_transform_is_separate_from_pattern_metadata():
    value = graph(); value.set_transform("right", Transform3D.translation(100, 0, 5))
    assert value.pieces["right"].outline == [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert value.assembly_transforms["right"].apply((1, 2, 3)) == (101.0, 2.0, 8.0)
    assert value.to_metadata()["assembly_transforms"][1][0] == "right"


def test_invalid_seam_piece_or_edge_is_rejected():
    value = SeamGraph(); value.add_piece(piece("left", "left"))
    with pytest.raises(ValueError, match="unknown pattern piece"): value.add_seam(Seam("left", 1, "missing", 0, id="bad"))
    value.add_piece(piece("right", "right"))
    with pytest.raises(ValueError, match="outside"): value.add_seam(Seam("left", 9, "right", 0, id="bad-edge"))


def test_arc_length_stitch_mapping_ignores_nonuniform_boundary_vertex_density():
    value = graph()
    edges = {("left", 1): (10, 11, 12, 13), ("right", 3): (20, 21, 22)}
    points = {
        ("left", 1): ((0.0, 0.0), (1.0, 0.0), (3.0, 0.0), (10.0, 0.0)),
        ("right", 3): ((0.0, 0.0), (5.0, 0.0), (10.0, 0.0)),
    }
    assert value.stitch_pairs(edges, edge_points=points) == ((10, 20), (12, 21), (13, 22))


def test_true_mn_arc_length_mapping_uses_member_ranges_and_nonuniform_sampling():
    from freecad_cloth.pattern.PatternModel import Seam

    value = SeamGraph()
    value.add_piece(piece("left", "left"))
    value.add_piece(piece("right", "right"))
    value.add_seam(
        Seam(
            "left", 1, "right", 3, id="mn-1",
            start_a=0.0, end_a=0.4, start_b=0.0, end_b=1.0,
            stitch_group="mn",
        )
    )
    value.add_seam(
        Seam(
            "left", 1, "right", 2, id="mn-2",
            start_a=0.4, end_a=1.0, start_b=0.0, end_b=1.0,
            stitch_group="mn",
        )
    )
    edges = {
        ("left", 1): (10, 11, 12, 13, 14, 15),
        ("right", 3): (20, 21, 22, 23),
        ("right", 2): (30, 31, 32, 33),
    }
    points = {
        ("left", 1): (
            (0.0, 0.0), (0.1, 0.0), (0.4, 0.0),
            (1.2, 0.0), (4.0, 0.0), (10.0, 0.0),
        ),
        ("right", 3): ((0.0, 0.0), (2.0, 0.0), (5.0, 0.0), (10.0, 0.0)),
        ("right", 2): ((0.0, 0.0), (1.0, 0.0), (4.0, 0.0), (10.0, 0.0)),
    }
    pairs = value.stitch_pairs(edges, edge_points=points)
    assert pairs == ((10, 20), (12, 21), (13, 22), (14, 23), (12, 30), (13, 31), (14, 32), (15, 33))


def test_true_mn_arc_length_mapping_reversal_is_explicit():
    from freecad_cloth.pattern.PatternModel import Seam

    value = SeamGraph()
    value.add_piece(piece("left", "left"))
    value.add_piece(piece("right", "right"))
    value.add_seam(
        Seam(
            "left", 1, "right", 3, id="mn-reverse",
            reversed_b=True, stitch_group="mn-reverse",
        )
    )
    edges = {("left", 1): (10, 11, 12, 13), ("right", 3): (20, 21, 22, 23)}
    points = {
        ("left", 1): ((0.0, 0.0), (1.0, 0.0), (3.0, 0.0), (10.0, 0.0)),
        ("right", 3): ((0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (12.0, 0.0)),
    }
    assert value.stitch_pairs(edges, edge_points=points) == ((10, 23), (12, 22), (13, 20))


def test_missing_mesh_edge_vertices_is_rejected():
    value = graph()
    with pytest.raises(ValueError, match="missing mesh edge"): value.stitch_pairs({("left", 1): (1, 2, 3)})

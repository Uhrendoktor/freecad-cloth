import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.sewing.SeamGraph import SeamGraph, Transform3D
from freecad_cloth.sewing.SewingNetwork import SewingMember, build_mn_seams


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



def test_curved_mn_correspondence_uses_physical_arc_length_with_nonuniform_spacing():
    seams = build_mn_seams(
        "mn",
        [SewingMember("left", 0), SewingMember("left", 1)],
        [SewingMember("right", 3)],
        lambda piece, edge: {("left", 0): 10.0, ("left", 1): 10.0, ("right", 3): 20.0}[(piece, edge)],
        alignment="uniform",
    )
    value = SeamGraph()
    value.add_piece(piece("left", "left"))
    value.add_piece(piece("right", "right"))
    for seam in seams:
        value.add_seam(seam)

    edge_vertices = {
        ("left", 0): (10, 11, 12),
        ("left", 1): (13, 14, 15),
        ("right", 3): (20, 21, 22, 23, 24, 25),
    }
    raw = (
        (0.0, 0.0),
        (0.8, 0.0),
        (5.0, 1.0),
        (10.0, 1.0),
        (14.5, 3.0),
        (19.5, 3.0),
    )
    total = sum(((b[0]-a[0])**2 + (b[1]-a[1])**2) ** 0.5 for a, b in zip(raw, raw[1:]))
    scale = 20.0 / total
    curved = tuple((x * scale, y * scale) for x, y in raw)
    edge_points = {
        ("left", 0): ((0.0, 0.0), (5.0, 0.0), (10.0, 0.0)),
        ("left", 1): ((10.0, 0.0), (15.0, 0.0), (20.0, 0.0)),
        ("right", 3): curved,
    }

    assert value.stitch_pairs(edge_vertices, edge_points=edge_points) == (
        (10, 20), (11, 22), (12, 23),
        (13, 23), (14, 24), (15, 25),
    )


def test_missing_mesh_edge_vertices_is_rejected():
    value = graph()
    with pytest.raises(ValueError, match="missing mesh edge"): value.stitch_pairs({("left", 1): (1, 2, 3)})

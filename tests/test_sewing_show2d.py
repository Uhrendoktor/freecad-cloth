import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.sewing.SewingCommands import show_sewing_2d
from freecad_cloth.sewing.SeamOverlay import _simulation_seam_geometry, _side_segments, seam_display_labels
from freecad_cloth.sewing.SewingCreationGui import viewport_edge_candidate
from freecad_cloth.sewing.SewingView import (
    apply_seam_colors,
    pattern_pieces_for_2d,
    seam_color_map,
    seam_visual_markers,
)


def test_2d_focus_includes_only_authoritative_pattern_pieces_in_document_order():
    first = SimpleNamespace(Name="PatternA", PatternType="PatternPiece")
    seam = SimpleNamespace(Name="Seam", SeamId="seam-1")
    second = SimpleNamespace(Name="PatternB", PatternType="PatternPiece")
    operation = SimpleNamespace(Name="Operation", SewingType="SewingOperation")
    assert pattern_pieces_for_2d([first, seam, second, operation]) == [first, second]


def test_2d_focus_ignores_unrelated_objects_without_freecad_runtime():
    objects = [
        SimpleNamespace(Name="Body"),
        SimpleNamespace(Name="Pattern", PatternType="PatternPiece"),
        SimpleNamespace(Name="Sketch"),
    ]
    result = pattern_pieces_for_2d(objects)
    assert [obj.Name for obj in result] == ["Pattern"]


def test_seam_colors_are_distinct_and_stable_by_seam_id():
    seam_ids = ["seam-3", "seam-1", "seam-2"]
    forward = seam_color_map(seam_ids)
    reverse = seam_color_map(reversed(seam_ids))
    assert forward == reverse
    assert len(set(forward.values())) == len(seam_ids)


def test_seam_colors_do_not_reassign_when_other_seams_are_added_or_removed():
    baseline = seam_color_map(["seam-2", "seam-3"])
    extended = seam_color_map(["seam-1", "seam-2", "seam-3", "seam-4"])
    reduced = seam_color_map(["seam-3"])
    assert extended["seam-2"] == baseline["seam-2"]
    assert extended["seam-3"] == baseline["seam-3"]
    assert reduced["seam-3"] == baseline["seam-3"]


def test_same_seam_id_always_maps_to_one_pair_identity_color():
    assert (
        seam_color_map(["pair-42", "pair-42"])["pair-42"]
        == seam_color_map(["pair-42", "pair-7"])["pair-42"]
    )


def test_seam_color_surface_contract_carries_identity_to_sewing_operations():
    source = (
        Path(__file__).resolve().parents[1] / "freecad_cloth" / "sewing" / "SewingObjects.py"
    ).read_text(encoding="utf-8")
    assert '"SeamId", "Sewing"' in source
    assert 'obj.SeamId = str(getattr(seam, "SeamId", "") or "")' in source
    assert "apply_seam_colors(doc.Objects)" in source


def test_apply_seam_colors_marks_each_seam_pair():
    first = SimpleNamespace(SeamId="seam-a", ViewObject=SimpleNamespace(LineColor=None))
    second = SimpleNamespace(SeamId="seam-b", ViewObject=SimpleNamespace(LineColor=None))
    colors = apply_seam_colors([second, first])
    assert first.ViewObject.LineColor == colors["seam-a"]
    assert second.ViewObject.LineColor == colors["seam-b"]
    assert first.ViewObject.LineColor != second.ViewObject.LineColor


def test_show_2d_does_not_select_seams_over_their_colors():
    seam = SimpleNamespace(SeamId="seam-1", ViewObject=SimpleNamespace(LineColor=None))
    piece = SimpleNamespace(PatternType="PatternPiece")

    class Selection:
        added = []
        cleared = 0

        @classmethod
        def clearSelection(cls):
            cls.cleared += 1

        @classmethod
        def addSelection(cls, obj):
            cls.added.append(obj)

    class View:
        def __init__(self):
            self.top = 0
            self.fit = 0

        def viewTop(self):
            self.top += 1

        def fitAll(self):
            self.fit += 1

    view = View()
    active = SimpleNamespace(
        Document=SimpleNamespace(Objects=[piece, seam]), activeView=lambda: view
    )
    gui = SimpleNamespace(Selection=Selection, activeDocument=lambda: active)
    previous_gui = sys.modules.get("FreeCADGui")
    sys.modules["FreeCADGui"] = gui
    try:
        show_sewing_2d()
    finally:
        if previous_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = previous_gui

    assert Selection.cleared == 1
    assert Selection.added == []
    assert view.top == 1
    assert view.fit == 1


def test_seam_visual_markers_are_deterministic_and_directional():
    a = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    b = ((0.0, 10.0, 0.0), (10.0, 10.0, 0.0), (20.0, 10.0, 0.0))
    first = seam_visual_markers(a, b)
    assert first == seam_visual_markers(a, b)
    assert len(first["correspondence"]) == 3
    assert first["direction_A"][1] == (1.0, 0.0)
    assert first["direction_B"][1] == (1.0, 0.0)
    assert first["notch_A"][1] == (-0.0, 1.0)


def test_seam_visual_markers_make_reversal_visible_in_b_direction_and_correspondence():
    a = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    b = ((20.0, 10.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0))
    markers = seam_visual_markers(a, b)
    assert markers["correspondence"][0][1] == b[0]
    assert markers["correspondence"][-1][1] == b[-1]
    assert markers["direction_A"][1] == (1.0, 0.0)
    assert markers["direction_B"][1] == (-1.0, 0.0)
    assert markers["notch_B"][1] == (0.0, -1.0)


def test_seam_visual_markers_reject_mismatched_correspondence():
    try:
        seam_visual_markers(((0.0, 0.0, 0.0),), ((0.0, 1.0, 0.0), (1.0, 1.0, 0.0)))
    except ValueError as exc:
        assert "equal length" in str(exc)
    else:
        raise AssertionError("marker builder must reject mismatched correspondence")


if __name__ == "__main__":
    test_2d_focus_includes_only_authoritative_pattern_pieces_in_document_order()
    test_2d_focus_ignores_unrelated_objects_without_freecad_runtime()
    test_seam_colors_are_distinct_and_stable_by_seam_id()
    test_seam_colors_do_not_reassign_when_other_seams_are_added_or_removed()
    test_same_seam_id_always_maps_to_one_pair_identity_color()
    test_apply_seam_colors_marks_each_seam_pair()
    test_show_2d_does_not_select_seams_over_their_colors()
    print("sewing Show 2D tests passed")


def test_seam_overlay_labels_are_unique_stable_pair_identifiers():
    initial_ids = ("seam-1", "seam-2", "custom-long-identity")
    baseline = seam_display_labels(initial_ids)
    extended = seam_display_labels((*initial_ids, "seam-3"))
    assert baseline["seam-1"] == "S1"
    assert len(set(extended.values())) == len(extended)
    for seam_id in initial_ids:
        assert extended[seam_id] == baseline[seam_id]


def test_seam_overlay_labels_resolve_short_name_collisions_without_merging_pairs():
    labels = seam_display_labels(("seam-1", "S1"))
    assert len(set(labels.values())) == 2
    assert all(labels[identity] for identity in ("seam-1", "S1"))


def test_viewport_picker_accepts_only_pattern_piece_edges():
    first = SimpleNamespace(Name="PatternA", Label="Front", PatternType="PatternPiece")
    second = SimpleNamespace(Name="PatternB", Label="Back", PatternType="PatternPiece")
    seam = SimpleNamespace(Name="Seam1", Label="Seam", SeamId="seam-1")
    document = SimpleNamespace(Objects=[first, second, seam])

    assert viewport_edge_candidate(
        document, {"Object": "PatternA", "Component": "Edge3"}
    ) == (first, "Edge3")
    assert viewport_edge_candidate(
        document, {"Object": "Back", "Component": "Edge2"}
    ) == (second, "Edge2")
    assert viewport_edge_candidate(
        document, {"Object": "PatternA", "Component": "Face1"}
    ) is None
    assert viewport_edge_candidate(
        document, {"Object": "Seam1", "Component": "Edge1"}
    ) is None
    assert viewport_edge_candidate(
        document, {"Object": "Missing", "Component": "Edge1"}
    ) is None


def test_simulation_seam_geometry_uses_authoritative_particle_pair_provenance():
    positions = (
        (0.0, 0.0, 4.0),
        (10.0, 0.0, 4.0),
        (0.0, 2.0, 4.0),
        (10.0, 2.0, 4.0),
    )
    backend = SimpleNamespace(positions=lambda: positions)
    proxy = SimpleNamespace(
        seam_stitch_pairs={"seam-7": ((0, 2), (1, 3))},
        backend=backend,
    )
    panel = SimpleNamespace(ViewObject=SimpleNamespace(Visibility=True))
    scene = SimpleNamespace(Proxy=proxy, DrapePanels=[panel])
    document = SimpleNamespace(Objects=[scene])

    geometry = _simulation_seam_geometry(document)
    side_a, side_b, connectors = geometry["seam-7"]
    assert side_a == [positions[0], positions[1]]
    assert side_b == [positions[2], positions[3]]
    assert connectors == [[positions[0], positions[2]], [positions[1], positions[3]]]


def test_simulation_seam_geometry_fails_closed_for_missing_or_stale_indices():
    backend = SimpleNamespace(positions=lambda: ((0.0, 0.0, 0.0),))
    proxy = SimpleNamespace(seam_stitch_pairs={"seam-1": ((0, 4),)}, backend=backend)
    panel = SimpleNamespace(ViewObject=SimpleNamespace(Visibility=True))
    scene = SimpleNamespace(Proxy=proxy, DrapePanels=[panel])
    assert _simulation_seam_geometry(SimpleNamespace(Objects=[scene])) == {}


def test_seam_side_overlay_creates_edge_direction_and_notch_strokes():
    points = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    segments = _side_segments(points)
    assert segments[0] == list(points)
    assert len(segments) >= 3
    assert all(len(segment) >= 2 for segment in segments)



import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece, Seam
from PatternSync import PatternSourceSnapshot, SimulationLockedError, SynchronizationState
from SeamGraph import SeamGraph, Transform3D


def _graph():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (10, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (10, 10)], id="back"))
    graph.add_seam(Seam("front", 0, "back", 0, id="side", alignment="uniform"))
    return graph


def test_snapshot_is_stable_for_equivalent_graphs():
    first = PatternSourceSnapshot.from_graph(_graph())
    second = PatternSourceSnapshot.from_graph(_graph())
    assert first.digest == second.digest
    assert first.diff(second).changed is False
    assert first.diff(second).requires_rebuild is False


def test_outline_edit_invalidates_piece_geometry():
    graph = _graph()
    before = PatternSourceSnapshot.from_graph(graph)
    graph.pieces["front"].outline[1] = (12, 0)
    after = PatternSourceSnapshot.from_graph(graph)
    delta = before.diff(after)
    assert delta.changed_pieces == ("front",)
    assert delta.changed_seams == ()
    assert delta.requires_rebuild is True


def test_seam_edit_invalidates_topology():
    graph = _graph()
    before = PatternSourceSnapshot.from_graph(graph)
    graph.seams["side"] = type(graph.seams["side"])(
        Seam("front", 0, "back", 0, id="side", reversed_b=True, alignment="uniform")
    )
    after = PatternSourceSnapshot.from_graph(graph)
    delta = before.diff(after)
    assert delta.changed_seams == ("side",)
    assert delta.requires_rebuild is True


def test_transform_only_edit_can_be_reprojected():
    graph = _graph()
    before = PatternSourceSnapshot.from_graph(graph)
    graph.set_transform("back", Transform3D.translation(25, 0, 0))
    after = PatternSourceSnapshot.from_graph(graph)
    delta = before.diff(after)
    assert delta.changed_pieces == ()
    assert delta.changed_seams == ()
    assert delta.changed_transforms == ("back",)
    assert delta.requires_rebuild is True
    assert delta.requires_reprojection is True


def test_snapshot_captures_seam_alignment_and_ranges():
    graph = _graph()
    graph.seams["side"] = type(graph.seams["side"])(
        Seam("front", 0, "back", 0, id="side", start_a=0.1, end_a=0.9, alignment="uniform")
    )
    snapshot = PatternSourceSnapshot.from_graph(graph)
    seam = snapshot.seams[0]
    assert seam[5:9] == (0.1, 0.9, 0.0, 1.0)
    assert seam[9:] == (False, "uniform", "", "plain")


def test_simulation_lifecycle_locks_source_edits():
    state = SynchronizationState()
    snapshot = PatternSourceSnapshot.from_graph(_graph())
    state.require_editable()
    state.begin(snapshot)
    assert state.simulation_active is True
    assert state.active_snapshot is snapshot
    try:
        state.require_editable()
    except SimulationLockedError:
        pass
    else:
        raise AssertionError("active simulation must lock source edits")
    state.end()
    assert state.simulation_active is False
    assert state.active_snapshot is None
    state.require_editable()

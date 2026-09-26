"""Focused contracts for the Simulation Quality task-panel UI."""

from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.FittingHandoff import fitting_stage_status
from freecad_cloth.simulation.SimulationQualityGui import target_is_blocked


ROOT = Path(__file__).resolve().parents[1]


def test_fitting_stage_status_reports_existing_persistent_state():
    class Document:
        def __init__(self, objects):
            self.Objects = tuple(objects)

    fitting = SimpleNamespace(
        FittingType="FittingScene",
        FitStatus="Pieces assigned",
        PatternPieces=("front", "back"),
        PiecePlacements=("front|0,0,0|0", "back|10,0,0|0"),
        ArrangementPoints=("shoulder|0,0,0|front|0|",),
        HomePlacements=("front|0,0,0|0", "back|10,0,0|0"),
    )
    simulation = SimpleNamespace(Document=Document((fitting,)))
    message, can_reset = fitting_stage_status(simulation)
    assert "Pieces assigned" in message
    assert "2 pieces assigned" in message
    assert "2/2 saved placement(s)" in message
    assert "1 arrangement point(s)" in message
    assert can_reset is True


def test_fitting_stage_status_does_not_invent_a_new_placement_validity_state():
    simulation = SimpleNamespace(Document=SimpleNamespace(Objects=()))
    message, can_reset = fitting_stage_status(simulation)
    assert message.startswith("Not arranged yet")
    assert can_reset is False


def test_target_blocking_contract_remains_fail_closed():
    assert target_is_blocked({"state": "ready"}) is False
    for state in ("stale", "unbuilt", "unassigned", "invalid", "missing", "disabled"):
        assert target_is_blocked({"state": state}) is True


def test_simulation_panel_and_handoff_surface_are_bounded_and_native():
    sim_source = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
    handoff_source = (ROOT / "freecad_cloth" / "simulation" / "FittingHandoff.py").read_text(encoding="utf-8")
    for marker in (
        'QtWidgets.QGroupBox("Arrange / Fit")',
        'QPushButton("Arrange / Fit…")',
        'QPushButton("Reset arrangement")',
        'QPushButton("Refresh target")',
        "fitting_stage_status",
        "open_arrange_fit_from_simulation",
        "reset_arrangement_from_simulation",
    ):
        assert marker in sim_source
    assert "ClothPieces" in handoff_source
    assert 'Gui.activateWorkbench("ClothSewingWorkbench")' in handoff_source
    assert "assign_avatar_source" not in handoff_source
    assert "DrapeTarget remains authoritative" in handoff_source

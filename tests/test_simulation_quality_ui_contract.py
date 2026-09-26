"""Focused source/unit contracts for the Simulation Quality task panel UI."""

from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityGui import fitting_status, target_is_blocked


ROOT = Path(__file__).resolve().parents[1]


def test_arrange_fit_summary_reports_document_facts_without_inventing_validity():
    assert fitting_status(None) == {
        "state": "missing",
        "message": "No Arrange & Fit scene is present.",
        "pieces": 0,
        "placements": 0,
        "points": 0,
        "can_reset": False,
    }

    scene = SimpleNamespace(
        FitStatus="Pieces assigned",
        PatternPieces=("front", "back"),
        PiecePlacements=("front|0,0,0|0",),
        ArrangementPoints=("shoulder|0,0,0|front|0|",),
        HomePlacements=("front|0,0,0|0", "back|0,0,0|0"),
    )
    info = fitting_status(scene)
    assert info["state"] == "present"
    assert info["pieces"] == 2
    assert info["placements"] == 1
    assert info["points"] == 1
    assert info["can_reset"] is True
    assert "Arrange/Fit: Pieces assigned" in info["message"]
    assert "1/2 saved placement(s)" in info["message"]


def test_target_blocking_contract_remains_fail_closed():
    assert target_is_blocked({"state": "ready"}) is False
    for state in ("stale", "unbuilt", "unassigned", "invalid", "missing", "disabled"):
        assert target_is_blocked({"state": state}) is True


def test_simulation_panel_exposes_arrangement_and_target_recovery_actions():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
    for marker in (
        'QtWidgets.QGroupBox("Context")',
        'QPushButton("Create Arrange & Fit scene")',
        'QPushButton("Reset arrangement")',
        'QPushButton("Refresh target")',
        "self.target_context",
        "self.placement_status",
        "self.arrange_button",
        "self.reset_arrangement_button",
        "self.refresh_target_button",
        "fitting_status(fitting)",
        "target_is_blocked(target_info)",
    ):
        assert marker in source


def test_simulation_pin_policy_is_visible_and_persisted():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationGui.py").read_text(encoding="utf-8")
    for marker in (
        'layout.addRow("Pin policy", self.pin_policy)',
        'self.pin_policy.addItem("None (pinless)", "none")',
        'self.scene.PinPolicy = str(self.pin_policy.currentData() or "auto")',
        'self.scene.PinSelection = [p.strip()',
    ):
        assert marker in source

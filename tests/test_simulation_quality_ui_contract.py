"""Focused contracts for the simulation Arrange/Fit and target-recovery UI."""

from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityGui import fitting_status, target_is_blocked


ROOT = Path(__file__).resolve().parents[1]


def test_fitting_status_reports_persisted_fitting_facts():
    assert fitting_status(None)["state"] == "missing"
    scene = SimpleNamespace(
        FitStatus="Target snapped",
        PatternPieces=("front", "back"),
        PiecePlacements=("front|0,0,0|0", "back|0,0,0|0"),
        ArrangementPoints=(),
        HomePlacements=("front|0,0,0|0", "back|0,0,0|0"),
    )
    info = fitting_status(scene)
    assert info["pieces"] == 2
    assert info["placements"] == 2
    assert info["can_reset"] is True
    assert "Arrange/Fit: Target snapped" in info["message"]


def test_target_recovery_stays_fail_closed():
    assert target_is_blocked({"state": "ready"}) is False
    for state in ("stale", "unbuilt", "unassigned", "invalid", "missing", "disabled"):
        assert target_is_blocked({"state": state}) is True


def test_simulation_quality_panel_exposes_primary_fit_and_recovery_actions():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
    for marker in (
        'QtWidgets.QGroupBox("Context")',
        'QPushButton("Create Arrange & Fit scene")',
        'QPushButton("Reset arrangement")',
        'QPushButton("Refresh target")',
        'Snap assigned pieces to target',
        "snap_pieces_to_target",
        "refresh_drape_target",
        "self.target_context",
        "self.placement_status",
    ):
        assert marker in source

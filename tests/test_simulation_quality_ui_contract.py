"""Focused UI contracts for the simulation Arrange/Fit and recovery journey."""

from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityGui import fitting_status, target_is_blocked


ROOT = Path(__file__).resolve().parents[1]


def test_fitting_status_reports_persisted_document_facts():
    assert fitting_status(None)["state"] == "missing"
    scene = SimpleNamespace(
        FitStatus="Snapped to target",
        PatternPieces=("front", "back"),
        PiecePlacements=("front|0,0,0|0", "back|0,0,0|0"),
        ArrangementPoints=(),
        HomePlacements=("front|0,0,0|0", "back|0,0,0|0"),
    )
    info = fitting_status(scene)
    assert info["pieces"] == 2
    assert info["placements"] == 2
    assert info["can_reset"] is True
    assert "Arrange/Fit: Snapped to target" in info["message"]


def test_target_recovery_remains_fail_closed():
    assert target_is_blocked({"state": "ready"}) is False
    for state in ("stale", "unbuilt", "unassigned", "invalid", "missing", "disabled"):
        assert target_is_blocked({"state": state}) is True


def test_simulation_quality_panel_exposes_arrange_fit_and_target_recovery():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
    for marker in (
        'QtWidgets.QGroupBox("Context")',
        'QPushButton("Create Arrange & Fit scene")',
        'QPushButton("Reset arrangement")',
        'QPushButton("Refresh target")',
        'Snap assigned pieces to target',
        "fitting_status(fitting)",
        "target_is_blocked(target_info)",
        "snap_pieces_to_target",
        "refresh_drape_target",
    ):
        assert marker in source

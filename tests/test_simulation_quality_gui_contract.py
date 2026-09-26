"""Static contract checks for the simulation quality task-panel UX."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
HANDOFF = (ROOT / "freecad_cloth" / "simulation" / "FittingHandoff.py").read_text(encoding="utf-8")


def test_quality_panel_captures_panel_open_state():
    assert "SNAPSHOT_PROPERTIES = (" in GUI
    assert '"QualityPreset"' in GUI
    assert '"FabricDensity"' in GUI
    assert '"AvatarSkinOffset"' in GUI
    assert '"Steps"' in GUI
    assert "def _capture_snapshot(self):" in GUI
    assert "self._snapshot = {name: getattr(self.scene, name)" in GUI


def test_quality_panel_cancel_restores_persistent_values_before_close():
    assert "def _restore_snapshot(self):" in GUI
    assert "setattr(self.scene, name, value)" in GUI
    assert "self.scene.Document.recompute()" in GUI
    assert "def reject(self):" in GUI
    assert "self._restore_snapshot()" in GUI


def test_quality_panel_accept_commits_new_panel_baseline():
    assert "def accept(self):" in GUI
    assert "self._parameters_changed(); self._capture_snapshot()" in GUI


def test_arrange_fit_bridge_reports_persisted_state_without_validity_claims():
    from types import SimpleNamespace
    from freecad_cloth.simulation.FittingHandoff import fitting_stage_status

    fitting = SimpleNamespace(
        FittingType="FittingScene",
        PatternPieces=(object(), object()),
        PiecePlacements=("a", "b"),
        ArrangementPoints=("p",),
        FitStatus="Ready",
        HomePlacements=("a", "b"),
    )
    simulation = SimpleNamespace(Document=SimpleNamespace(Objects=(fitting,)))
    message, can_reset = fitting_stage_status(simulation)

    assert message == "Ready | 2 pieces assigned | 2/2 saved placement(s) | 1 arrangement point(s)"
    assert can_reset is True
    assert "valid" not in message.lower()
    assert "invalid" not in message.lower()


def test_arrange_fit_bridge_keeps_reset_syntax_and_uses_existing_handoff_only():
    assert "def reset_arrangement(self):\n        try:" not in GUI
    assert "def reset_arrangement(self):
        try:" in GUI
    assert "open_arrange_fit_from_simulation" in GUI
    assert "reset_arrangement_from_simulation" in GUI
    assert "refresh_drape_target" in GUI
    assert "fitting.DrapeTarget = target" not in HANDOFF

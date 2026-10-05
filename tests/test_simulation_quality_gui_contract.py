"""Static contract checks for the simulation quality task-panel UX."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(
    encoding="utf-8"
)


def test_quality_panel_captures_panel_open_state():
    assert "SNAPSHOT_PROPERTIES = (" in GUI
    assert '"QualityPreset"' in GUI
    assert '"FabricDensity"' in GUI
    assert '"AvatarSkinOffset"' in GUI
    assert '"Steps"' in GUI
    assert "def _capture_snapshot(self):" in GUI
    assert "self._snapshot = {" in GUI
    assert "getattr(self.scene, name)" in GUI


def test_quality_panel_cancel_restores_persistent_values_before_close():
    assert "def _restore_snapshot(self):" in GUI
    assert "setattr(self.scene, name, value)" in GUI
    assert "self.scene.Document.recompute()" in GUI
    assert "def reject(self):" in GUI
    assert "self._restore_snapshot()" in GUI


def test_quality_panel_accept_commits_new_panel_baseline():
    assert "def accept(self):" in GUI
    accept = GUI.split("def accept(self):", 1)[1].split("def reject(self):", 1)[0]
    assert "self._parameters_changed()" in accept
    assert "self._capture_snapshot()" in accept


def test_quality_panel_hides_precision_controls_by_default():
    assert 'self.advanced_toggle = QtWidgets.QToolButton()' in GUI
    assert 'self.advanced_toggle.setChecked(False)' in GUI
    assert 'self._set_expert_visibility(False)' in GUI
    assert 'Normal fitting uses presets.' in GUI

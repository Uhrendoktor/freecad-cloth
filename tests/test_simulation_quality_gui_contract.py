"""Behavioral checks for simulation quality task-panel state management."""

from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
from freecad_cloth.simulation.SimulationQualityRuntime import (
    PHYSICAL_MATERIAL_CONTROLS_SUPPORTED,
    PHYSICAL_MATERIAL_CONTROLS_UNSUPPORTED_MESSAGE,
)


def _scene():
    values = {
        name: value
        for name, value in zip(
            SimulationQualityTaskPanel.SNAPSHOT_PROPERTIES,
            range(1, len(SimulationQualityTaskPanel.SNAPSHOT_PROPERTIES) + 1),
        )
    }
    values["Document"] = SimpleNamespace(recompute=lambda: None)
    return SimpleNamespace(**values)


def test_snapshot_property_set_is_unique_and_covers_persistent_controls():
    properties = SimulationQualityTaskPanel.SNAPSHOT_PROPERTIES
    assert len(properties) == len(set(properties))
    assert "QualityPreset" in properties
    assert "FabricDensity" in properties
    assert "AvatarSkinOffset" in properties
    assert "Steps" in properties
    assert "PinMode" in properties


def test_capture_snapshot_records_only_existing_scene_properties():
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    scene = _scene()
    delattr(scene, "PinMode")
    panel.scene = scene
    panel._capture_snapshot()
    assert "PinMode" not in panel._snapshot
    assert panel._snapshot["QualityPreset"] == 1


def test_restore_snapshot_reverts_all_captured_values_and_recomputes():
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    scene = _scene()
    panel.scene = scene
    panel._load_widgets_only = lambda: None
    panel._refresh = lambda *args: None
    panel._capture_snapshot()
    original = dict(panel._snapshot)
    scene.Steps = 999
    scene.FabricDensity = 999
    recomputes = []
    scene.Document.recompute = lambda: recomputes.append("recompute")
    panel._restore_snapshot()
    assert scene.Steps == original["Steps"]
    assert scene.FabricDensity == original["FabricDensity"]
    assert recomputes == ["recompute"]


def test_accept_refreshes_the_panel_baseline_after_parameter_changes():
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = _scene()
    calls = []
    panel._parameters_changed = lambda: calls.append("parameters")
    panel._capture_snapshot = lambda: calls.append("snapshot")
    assert panel.accept() is True
    assert calls == ["parameters", "snapshot"]


def test_reject_restores_snapshot_before_closing_dialog():
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = _scene()
    calls = []
    panel._restore_snapshot = lambda: calls.append("restore")
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: object(),
        Control=SimpleNamespace(
            activeDialog=lambda: object(),
            closeDialog=lambda: calls.append("close"),
        ),
    )
    assert panel.reject() is True
    assert calls == ["restore", "close"]


def test_physical_material_controls_are_explicitly_unsupported_without_a_solver_mapping():
    assert PHYSICAL_MATERIAL_CONTROLS_SUPPORTED is False
    assert "PositionBasedDynamics solver" in PHYSICAL_MATERIAL_CONTROLS_UNSUPPORTED_MESSAGE
    assert "not consumed" in PHYSICAL_MATERIAL_CONTROLS_UNSUPPORTED_MESSAGE
    source = (
        Path(__file__).resolve().parents[1]
        / "freecad_cloth"
        / "simulation"
        / "SimulationQualityGui.py"
    ).read_text(encoding="utf-8")
    assert "_set_physical_material_controls_enabled(" in source
    assert "PHYSICAL_MATERIAL_CONTROLS_SUPPORTED" in source


def test_disabling_physical_material_controls_also_disables_form_labels():
    class Control:
        def __init__(self):
            self.enabled = True

        def setEnabled(self, enabled):
            self.enabled = enabled

    density = Control()
    stretch = Control()
    labels = {density: Control(), stretch: Control()}
    form = SimpleNamespace(labelForField=lambda widget: labels[widget])

    SimulationQualityTaskPanel._set_physical_material_controls_enabled(
        form, (density, stretch), False
    )

    assert density.enabled is False
    assert stretch.enabled is False
    assert labels[density].enabled is False
    assert labels[stretch].enabled is False

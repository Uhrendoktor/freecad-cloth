"""Behavioral checks for simulation quality task-panel state management."""

from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel


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


def test_avatar_attachment_controls_write_semantic_anchors_to_scene():
    recomputes = []
    scene = SimpleNamespace(
        Document=SimpleNamespace(recompute=lambda: recomputes.append("recompute"))
    )
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = scene
    panel._fabric_qcolor = None
    panel._refresh = lambda _message: None
    panel.pin_mode = SimpleNamespace(currentText=lambda: "Avatar Attachment")
    panel.attachment_offset = SimpleNamespace(value=lambda: 7.5)
    panel.attachment_anchors = SimpleNamespace(
        text=lambda: (
            "FrontPiece|edge-right|shoulder_right; "
            "BackPiece|edge-left|shoulder_left"
        )
    )
    for name, value in {
        "particle_distance": 4.0,
        "iterations": 8,
        "substeps": 1,
        "density": 150.0,
        "thickness": 0.5,
        "stretch": 0.02,
        "shear": 0.02,
        "bend": 0.01,
        "friction": 0.5,
        "specular": 0.25,
        "roughness": 0.65,
        "transparency": 0,
        "skin_offset": 0.0,
        "collision_radius": 2.0,
    }.items():
        setattr(panel, name, SimpleNamespace(value=lambda value=value: value))

    panel._parameters_changed()

    assert scene.PinMode == "Avatar Attachment"
    assert scene.AttachmentOffset == 7.5
    assert scene.AvatarAttachmentAnchors == [
        "FrontPiece|edge-right|shoulder_right",
        "BackPiece|edge-left|shoulder_left",
    ]
    assert recomputes == ["recompute"]


def test_pin_mode_change_shows_and_hides_attachment_controls():
    class VisibilityControl:
        def setVisible(self, visible):
            self.visible = visible

    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.attachment_offset = VisibilityControl()
    panel.attachment_anchors = VisibilityControl()
    panel.attachment_offset_label = VisibilityControl()
    panel.attachment_anchors_label = VisibilityControl()
    changes = []
    panel._parameters_changed = lambda: changes.append("applied")

    panel._pin_mode_changed("Avatar Attachment")
    assert panel.attachment_offset.visible is True
    assert panel.attachment_anchors.visible is True
    assert panel.attachment_offset_label.visible is True
    assert panel.attachment_anchors_label.visible is True

    panel._pin_mode_changed("None")
    assert panel.attachment_offset.visible is False
    assert panel.attachment_anchors.visible is False
    assert panel.attachment_offset_label.visible is False
    assert panel.attachment_anchors_label.visible is False
    assert changes == ["applied", "applied"]

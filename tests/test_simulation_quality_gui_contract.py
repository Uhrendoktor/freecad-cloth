# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral checks for simulation quality task-panel state management."""

from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
from tests.support.assertions import require


def _scene() -> SimpleNamespace:
    """Build a FreeCAD-like scene with all persisted quality controls.

    Returns:
        A namespace with deterministic snapshot values and a fake document.
    """
    values: dict[str, object] = dict(
        zip(
            SimulationQualityTaskPanel.SNAPSHOT_PROPERTIES,
            range(1, len(SimulationQualityTaskPanel.SNAPSHOT_PROPERTIES) + 1),
            strict=True,
        )
    )
    values["Document"] = SimpleNamespace(recompute=lambda: None)
    return SimpleNamespace(**values)


def test_snapshot_property_set_is_unique_and_covers_persistent_controls() -> None:
    """Keep the snapshot schema unique and cover persisted quality controls."""
    properties = SimulationQualityTaskPanel.SNAPSHOT_PROPERTIES
    require(
        condition=len(properties) == len(set(properties)),
        message="Snapshot property names must be unique.",
    )
    for name in (
        "QualityPreset",
        "FabricDensity",
        "AvatarSkinOffset",
        "Steps",
        "PinMode",
    ):
        require(
            condition=name in properties,
            message=f"Snapshot schema must include {name}.",
        )


def test_capture_snapshot_records_only_existing_scene_properties() -> None:
    """Skip controls that are absent from a scene when capturing its snapshot."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    scene = _scene()
    del scene.PinMode
    panel.scene = scene
    panel._capture_snapshot()
    snapshot = panel._snapshot
    if snapshot is None:
        raise RuntimeError("Snapshot capture must initialize the snapshot state.")
    require(
        condition="PinMode" not in snapshot,
        message="Snapshot capture must skip absent scene properties.",
    )
    require(
        condition=snapshot["QualityPreset"] == 1,
        message="Snapshot capture must retain existing property values.",
    )


def test_restore_snapshot_reverts_all_captured_values_and_recomputes() -> None:
    """Restore captured values and recompute the document exactly once."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    scene = _scene()
    panel.scene = scene
    panel._load_widgets_only = lambda: None
    panel._refresh = lambda *args: None
    panel._capture_snapshot()
    snapshot = panel._snapshot
    if snapshot is None:
        raise RuntimeError("Snapshot capture must initialize the snapshot state.")
    original = dict(snapshot)
    scene.Steps = 999
    scene.FabricDensity = 999
    recomputes: list[str] = []
    scene.Document.recompute = lambda: recomputes.append("recompute")
    panel._restore_snapshot()
    require(
        condition=scene.Steps == original["Steps"],
        message="Restoring a snapshot must restore the step count.",
    )
    require(
        condition=scene.FabricDensity == original["FabricDensity"],
        message="Restoring a snapshot must restore fabric density.",
    )
    require(
        condition=recomputes == ["recompute"],
        message="Restoring a snapshot must recompute the document once.",
    )


def test_accept_refreshes_the_panel_baseline_after_parameter_changes() -> None:
    """Refresh the panel snapshot after accepting edited parameters."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = _scene()
    calls: list[str] = []
    panel._parameters_changed = lambda: calls.append("parameters")
    panel._capture_snapshot = lambda: calls.append("snapshot")
    require(
        condition=panel.accept() is True,
        message="Accepting the panel must report success.",
    )
    require(
        condition=calls == ["parameters", "snapshot"],
        message="Accepting the panel must update parameters before capturing a snapshot.",
    )


def test_reject_restores_snapshot_before_closing_dialog() -> None:
    """Restore original values before the rejected task panel closes."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = _scene()
    calls: list[str] = []
    panel._restore_snapshot = lambda: calls.append("restore")
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: object(),
        Control=SimpleNamespace(
            activeDialog=lambda: object(),
            closeDialog=lambda: calls.append("close"),
        ),
    )
    require(
        condition=panel.reject() is True,
        message="Rejecting the panel must report success.",
    )
    require(
        condition=calls == ["restore", "close"],
        message="Rejecting the panel must restore values before closing the dialog.",
    )

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral checks for simulation quality task-panel state management."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest

from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
from tests.support.assertions import require, require_not_none


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



def _panel_method(
    panel: SimulationQualityTaskPanel,
    name: str,
) -> Callable[..., object]:
    """Retrieve a panel method by name for behavior-focused contract tests.

    Args:
        panel: Task panel whose behavior is under test.
        name: Method name exposed by the panel.

    Returns:
        The bound panel method as a callable.
    """
    return cast("Callable[..., object]", getattr(panel, name))


def _snapshot(panel: SimulationQualityTaskPanel) -> dict[str, object]:
    """Return the panel's captured values for snapshot contract checks.

    Args:
        panel: Task panel whose snapshot was captured.

    Returns:
        The captured snapshot mapping.

    """
    snapshot = cast("dict[str, object] | None", getattr(panel, "_snapshot", None))
    return require_not_none(
        snapshot,
        message="Snapshot capture must initialize the snapshot state.",
    )

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
    _panel_method(panel, "_capture_snapshot")()
    snapshot = _snapshot(panel)
    require(
        condition="PinMode" not in snapshot,
        message="Snapshot capture must skip absent scene properties.",
    )
    require(
        condition=snapshot["QualityPreset"] == 1,
        message="Snapshot capture must retain existing property values.",
    )


def test_restore_snapshot_reverts_all_captured_values_and_recomputes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore captured values and recompute the document exactly once."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    scene = _scene()
    panel.scene = scene

    def load_widgets_only() -> None:
        """Stand in for widget synchronization during snapshot restoration."""

    def refresh(message: str | None = None) -> None:
        """Stand in for UI refresh during snapshot restoration."""

        _ = message

    monkeypatch.setattr(panel, "_load_widgets_only", load_widgets_only)
    monkeypatch.setattr(panel, "_refresh", refresh)
    _panel_method(panel, "_capture_snapshot")()
    original = dict(_snapshot(panel))
    scene.Steps = 999
    scene.FabricDensity = 999
    recomputes: list[str] = []
    scene.Document.recompute = lambda: recomputes.append("recompute")
    _panel_method(panel, "_restore_snapshot")()
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


def test_accept_refreshes_the_panel_baseline_after_parameter_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh the panel snapshot after accepting edited parameters."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = _scene()
    calls: list[str] = []

    def parameters_changed() -> None:
        """Record parameter refresh in the fake panel."""

        calls.append("parameters")

    def capture_snapshot() -> None:
        """Record snapshot capture in the fake panel."""

        calls.append("snapshot")

    monkeypatch.setattr(panel, "_parameters_changed", parameters_changed)
    monkeypatch.setattr(panel, "_capture_snapshot", capture_snapshot)
    require(
        condition=panel.accept() is True,
        message="Accepting the panel must report success.",
    )
    require(
        condition=calls == ["parameters", "snapshot"],
        message="Accepting the panel must update parameters before capturing a snapshot.",
    )


def test_reject_restores_snapshot_before_closing_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore original values before the rejected task panel closes."""
    panel = SimulationQualityTaskPanel.__new__(SimulationQualityTaskPanel)
    panel.scene = _scene()
    calls: list[str] = []

    def restore_snapshot() -> None:
        """Record snapshot restoration in the fake panel."""

        calls.append("restore")

    def active_document() -> object:
        """Return a non-null fake active document."""

        return object()

    def active_dialog() -> object:
        """Return a non-null fake active dialog."""

        return object()

    def close_dialog() -> None:
        """Record closing the fake task-panel dialog."""

        calls.append("close")

    monkeypatch.setattr(panel, "_restore_snapshot", restore_snapshot)
    monkeypatch.setattr(
        panel,
        "Gui",
        SimpleNamespace(
            activeDocument=active_document,
            Control=SimpleNamespace(
                activeDialog=active_dialog,
                closeDialog=close_dialog,
            ),
        ),
        raising=False,
    )
    require(
        condition=panel.reject() is True,
        message="Rejecting the panel must report success.",
    )
    require(
        condition=calls == ["restore", "close"],
        message="Rejecting the panel must restore values before closing the dialog.",
    )

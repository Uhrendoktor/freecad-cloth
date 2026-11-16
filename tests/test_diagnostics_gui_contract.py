# Copyright (C) 2026 FreeCAD Cloth contributors
"""Focused behavior checks for the diagnostics task-panel frontend."""

from collections.abc import Callable
from types import ModuleType
from typing import cast

import pytest

from freecad_cloth.simulation import ClothDiagnostics, ClothDiagnosticsGui


class _Signal:
    """Small signal double used to exercise live metric-selection updates."""

    def __init__(self) -> None:
        self.callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        self.callbacks.append(callback)

    def emit(self, *args: object) -> None:
        for callback in self.callbacks:
            callback(*args)


class _Widget:
    """Shared headless widget surface used by the diagnostics panel."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.enabled = True
        self.properties: dict[str, str] = {}
        self.wrapped = False

    def setText(self, text: str) -> None:
        self.text = str(text)

    def setWordWrap(self, enabled: bool) -> None:
        self.wrapped = bool(enabled)

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def setProperty(self, name: str, value: str) -> None:
        self.properties[name] = value

    def style(self) -> None:
        return None

    def update(self) -> None:
        return None


class _ComboBox(_Widget):
    """Metric selector that emits the newly selected label."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[str] = []
        self.current = ""
        self.currentTextChanged = _Signal()

    def addItems(self, items: tuple[str, ...]) -> None:
        self.items.extend(items)
        if items:
            self.current = items[0]

    def currentText(self) -> str:
        return self.current

    def setCurrentText(self, value: str) -> None:
        self.current = value
        self.currentTextChanged.emit(value)


class _Button(_Widget):
    """Action button with a signal and observable enabled state."""

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.clicked = _Signal()


class _Layout:
    """Vertical layout double sufficient for assembling the task panel."""

    def __init__(self, *_args: object) -> None:
        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        self.widgets.append(widget)

    def addStretch(self, _stretch: int = 0) -> None:
        return None


class _MetricResult:
    """Result fixture returning stable values for each supported metric."""

    @staticmethod
    def metric(name: str) -> tuple[float, ...]:
        return {
            "stress": (1.0, 3.0),
            "strain": (0.1, 0.3),
            "fit": (0.8, 0.9),
            "pressure": (2.0, 4.0),
        }[name]


def _install_panel_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install headless Qt and analysis collaborators for focused panel tests."""
    widgets = ModuleType("ClothDiagnosticsTestQtWidgets")
    for name, value in (
        ("QWidget", _Widget),
        ("QVBoxLayout", _Layout),
        ("QGroupBox", _Widget),
        ("QComboBox", _ComboBox),
        ("QLabel", _Widget),
        ("QPushButton", _Button),
    ):
        setattr(widgets, name, value)

    monkeypatch.setattr(
        ClothDiagnosticsGui,
        "_qt",
        lambda: (cast("ModuleType", object()), cast("ModuleType", object()), widgets),
    )
    monkeypatch.setattr(
        ClothDiagnosticsGui,
        "_simulation_data",
        lambda _scene: [(object(), (), _MetricResult())],
    )
    monkeypatch.setattr(
        ClothDiagnostics,
        "metric_definition",
        lambda metric: {"formula": f"{metric} formula", "units": "unit"},
    )
    monkeypatch.setattr(ClothDiagnostics, "summarize", lambda _result: "summary")


def test_metric_selection_refreshes_definition_range_and_action_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing the metric immediately updates the summary and keeps actions available."""
    _install_panel_dependencies(monkeypatch)
    panel = ClothDiagnosticsGui.DiagnosticsTaskPanel(cast("object", object()))

    assert panel.definition.text == "Formula: stress formula | Units: unit | Read-only derived analysis"
    assert panel.status.text.startswith("Stress map: 2 faces")
    assert panel.map_button.enabled is True
    assert panel.export_button.enabled is True

    panel.metric.setCurrentText("strain")

    assert panel.definition.text == "Formula: strain formula | Units: unit | Read-only derived analysis"
    assert panel.status.text.startswith("Strain map: 2 faces")
    assert panel.map_button.enabled is True
    assert panel.export_button.enabled is True


def test_analysis_failure_disables_map_and_export_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not leave actions enabled when current simulation data cannot be analysed."""
    _install_panel_dependencies(monkeypatch)

    def unavailable(_scene: object) -> list[object]:
        raise RuntimeError("run the simulation before opening diagnostics")

    monkeypatch.setattr(ClothDiagnosticsGui, "_simulation_data", unavailable)
    panel = ClothDiagnosticsGui.DiagnosticsTaskPanel(cast("object", object()))

    assert panel.map_button.enabled is False
    assert panel.export_button.enabled is False
    assert panel.status.text == "run the simulation before opening diagnostics"
    assert panel.status.properties["clothState"] == "error"

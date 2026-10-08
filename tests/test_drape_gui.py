"""Behavioral tests for the native DrapeTarget task-panel frontend."""

from types import SimpleNamespace

import pytest

from freecad_cloth.simulation import DrapeGui


class _Combo:
    def __init__(self, index=-1):
        self.index = index
        self.items = []
        self.blocked = []

    def clear(self):
        self.items.clear()
        self.index = -1

    def addItem(self, value):
        self.items.append(value)

    def currentIndex(self):
        return self.index

    def setCurrentIndex(self, value):
        self.index = value

    def setCurrentText(self, value):
        self.index = self.items.index(value)

    def currentText(self):
        return self.items[self.index]

    def blockSignals(self, value):
        self.blocked.append(bool(value))


class _Scalar:
    def __init__(self, value=0.0):
        self._value = value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value

    def isChecked(self):
        return bool(self._value)

    def setChecked(self, value):
        self._value = bool(value)


class _Status:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = str(value)


def _panel():
    panel = DrapeGui.DrapeTargetTaskPanel.__new__(DrapeGui.DrapeTargetTaskPanel)
    panel.target = object()
    panel.source = _Combo()
    panel.target_type = _Combo(0)
    panel.target_type.items = ["FreeCAD Geometry"]
    panel.preset = _Combo(1)
    panel.preset.items = ["Preview", "Normal", "Final"]
    panel.deflection = _Scalar(1.0)
    panel.thickness = _Scalar(2.0)
    panel.enabled = _Scalar(True)
    panel.status = _Status()
    panel._source_objects = []
    panel._loading = False
    return panel


def test_presets_are_explicit_and_materially_distinct():
    assert DrapeGui.DrapeTargetTaskPanel.PRESETS == (
        ("Preview", 2.5),
        ("Normal", 1.0),
        ("Final", 0.35),
    )


def test_populate_sources_keeps_only_collision_capable_objects():
    panel = _panel()
    panel.target = object()
    avatar = SimpleNamespace(AvatarType="ClothAvatar", Label="Avatar")
    shape = SimpleNamespace(Shape=object(), Label="Shape")
    mesh = SimpleNamespace(Mesh=object(), Label="Mesh")
    ignored = SimpleNamespace(Label="Ignored")
    panel.doc = SimpleNamespace(Objects=(panel.target, avatar, shape, mesh, ignored))

    panel._populate_sources()

    assert panel._source_objects == [avatar, shape, mesh]
    assert panel.source.items == ["Avatar", "Shape", "Mesh"]


def test_source_selection_is_bounds_checked():
    panel = _panel()
    source = object()
    panel._source_objects = [source]

    panel.source.index = 0
    assert panel._selected_source() is source

    panel.source.index = -1
    assert panel._selected_source() is None

    panel.source.index = 2
    assert panel._selected_source() is None


def test_nearest_preset_and_preset_change_update_deflection():
    panel = _panel()

    panel._select_nearest_preset(1.2)
    assert panel.preset.index == 1

    panel.preset = _Combo()
    panel.preset.items = ["Preview", "Normal", "Final"]
    panel._preset_changed("Final")
    assert panel.deflection.value() == pytest.approx(0.35)
    assert "Staged target edits" in panel.status.text


def test_missing_target_disables_apply_and_reports_action():
    panel = _panel()
    panel.target = None
    panel.apply_button = SimpleNamespace(setEnabled=lambda value: setattr(panel, "_apply_enabled", value))

    panel.doc = SimpleNamespace()
    panel._load()

    assert panel._apply_enabled is False
    assert "Create a Drape Target first" in panel.status.text


def test_apply_persists_target_values_and_recomputes(monkeypatch):
    panel = _panel()
    source = object()
    target = SimpleNamespace(CollisionDeflection=1.0, CollisionThickness=2.0, Enabled=True)
    document_calls = []
    assigned = []

    panel.target = target
    panel.source = _Combo(0)
    panel.target_type = _Combo()
    panel.target_type.items = ["FreeCAD Geometry"]
    panel.target_type.index = 0
    panel.deflection.setValue(0.35)
    panel.thickness.setValue(3.0)
    panel.enabled.setChecked(False)
    panel._source_objects = [source]
    panel.doc = SimpleNamespace(recompute=lambda: document_calls.append("recompute"))

    monkeypatch.setattr(
        "freecad_cloth.simulation.DrapeTarget.assign_drape_target",
        lambda target_obj, source_obj, target_type: assigned.append(
            (target_obj, source_obj, target_type)
        ),
    )

    assert panel._apply() is True
    assert (target.CollisionDeflection, target.CollisionThickness, target.Enabled) == (
        0.35,
        3.0,
        False,
    )
    assert assigned == [(target, source, "FreeCAD Geometry")]
    assert document_calls == ["recompute"]


def test_apply_fails_closed_without_selected_source():
    panel = _panel()
    panel.doc = SimpleNamespace(recompute=lambda: None)
    panel.source = _Combo(-1)
    panel.target_type = _Combo()
    panel.target_type.items = ["FreeCAD Geometry"]
    panel.target_type.index = 0

    assert panel._apply() is False
    assert "Select a collision object" in panel.status.text


def test_staged_preview_status_is_diagnostic_only():
    panel = _panel()
    panel._preview_status()
    assert (
        panel.status.text
        == "Staged target edits. Apply & Refresh to rebuild collision geometry; "
        "Cancel leaves the document unchanged."
    )


def test_refresh_status_reports_state_and_invalidation_reason():
    panel = _panel()
    panel.target = SimpleNamespace(TargetStatus="stale", InvalidationReason="source changed")

    panel._refresh_status()

    assert panel.status.text == "Target status: stale — source changed"


def test_reject_closes_active_dialog():
    panel = _panel()
    calls = []
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: object(),
        Control=SimpleNamespace(activeDialog=lambda: object(), closeDialog=lambda: calls.append("close")),
    )

    assert panel.reject() is True
    assert calls == ["close"]

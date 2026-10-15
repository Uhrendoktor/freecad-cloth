"""Tests for the Qt UI design helpers that do not require a FreeCAD runtime."""

import sys
from collections.abc import Callable
from types import ModuleType, SimpleNamespace

import pytest

from freecad_cloth.common.UiDesign import (
    PANEL_STYLE,
    apply_panel_style,
    make_disclosure,
    mark_button,
    set_status,
)


class _Style:
    """Minimal Qt style stub that records the dynamic-property refresh lifecycle."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def unpolish(self, widget: object) -> None:
        self.events.append(("unpolish", widget))

    def polish(self, widget: object) -> None:
        self.events.append(("polish", widget))


class _Label:
    """Minimal status-label stub for behavior that is independent of Qt."""

    def __init__(self) -> None:
        self.text: str = ""
        self.properties: dict[str, str] = {}
        self.wrap: bool = False
        self.events: list[str] = []
        self._style: _Style = _Style()

    def setText(self, value: str) -> None:
        self.text = value

    def setWordWrap(self, value: bool) -> None:
        self.wrap = value

    def setProperty(self, name: str, value: str) -> None:
        self.properties[name] = value

    def style(self) -> _Style:
        return self._style

    def update(self) -> None:
        self.events.append("update")


def test_set_status_sets_text_semantic_state_and_wrap() -> None:
    label = _Label()

    set_status(label, "Select two edges, then Preview.", state="warning")

    assert label.text == "Select two edges, then Preview."
    assert label.wrap is True
    assert label.properties == {"clothRole": "status", "clothState": "warning"}
    assert [event[0] for event in label._style.events] == ["unpolish", "polish"]
    assert label.events == ["update"]


def test_set_status_falls_back_to_info_for_unknown_states() -> None:
    label = _Label()

    set_status(label, "Ready", state="unexpected")

    assert label.properties["clothState"] == "info"


def test_mark_button_assigns_role_and_refreshes_style() -> None:
    class _Button(_Label):
        pass

    button = _Button()
    mark_button(button, "primary")

    assert button.properties["clothEmphasis"] == "primary"
    assert [event[0] for event in button._style.events] == ["unpolish", "polish"]


def test_apply_panel_style_scopes_stylesheet_and_normalizes_layouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _QtLayout:
        pass

    class _Layout:
        def __init__(self) -> None:
            self.margins: tuple[int, int, int, int] | None = None
            self.spacing: int | None = None

        def setContentsMargins(self, left: int, top: int, right: int, bottom: int) -> None:
            self.margins = (left, top, right, bottom)

        def setSpacing(self, spacing: int) -> None:
            self.spacing = spacing

    class _Panel:
        def __init__(self) -> None:
            self.stylesheet = ""
            self.outer_layout = _Layout()
            self.nested_layouts = [_Layout()]
            self.requested_child_type: type[object] | None = None

        def setStyleSheet(self, stylesheet: str) -> None:
            self.stylesheet = stylesheet

        def layout(self) -> _Layout:
            return self.outer_layout

        def findChildren(self, widget_type: type[object]) -> list[_Layout]:
            self.requested_child_type = widget_type
            return self.nested_layouts

    pyside = ModuleType("PySide")
    pyside.QtWidgets = SimpleNamespace(QLayout=_QtLayout)
    monkeypatch.setitem(sys.modules, "PySide", pyside)

    panel = _Panel()
    apply_panel_style(panel)

    assert panel.stylesheet == PANEL_STYLE
    assert panel.outer_layout.margins == (8, 8, 8, 8)
    assert panel.outer_layout.spacing == 6
    assert panel.requested_child_type is _QtLayout
    assert panel.nested_layouts[0].spacing == 6


def test_make_disclosure_toggles_content_and_arrow() -> None:
    class _Signal:
        def __init__(self) -> None:
            self.callback: Callable[[bool], None] | None = None

        def connect(self, callback: Callable[[bool], None]) -> None:
            self.callback = callback

        def emit(self, value: bool) -> None:
            if self.callback is not None:
                self.callback(value)

    class _Widget:
        def __init__(self, *_args: object) -> None:
            self.visible: bool | None = None

        def setVisible(self, visible: bool) -> None:
            self.visible = visible

    class _Layout:
        def __init__(self, _parent: object) -> None:
            self.margins: tuple[int, int, int, int] | None = None
            self.spacing: int | None = None
            self.widgets: list[object] = []

        def setContentsMargins(self, left: int, top: int, right: int, bottom: int) -> None:
            self.margins = (left, top, right, bottom)

        def setSpacing(self, spacing: int) -> None:
            self.spacing = spacing

        def addWidget(self, widget: object) -> None:
            self.widgets.append(widget)

    class _ToolButton(_Widget):
        def __init__(self, parent: object | None = None) -> None:
            super().__init__(parent)
            self.text = ""
            self.checkable = False
            self.checked = False
            self.arrow: object | None = None
            self.tooltip = ""
            self.style: object | None = None
            self.toggled = _Signal()

        def setText(self, text: str) -> None:
            self.text = text

        def setCheckable(self, checkable: bool) -> None:
            self.checkable = checkable

        def setChecked(self, checked: bool) -> None:
            checked = bool(checked)
            if checked != self.checked:
                self.checked = checked
                self.toggled.emit(checked)

        def setArrowType(self, arrow: object) -> None:
            self.arrow = arrow

        def setToolButtonStyle(self, style: object) -> None:
            self.style = style

        def setToolTip(self, tooltip: str) -> None:
            self.tooltip = tooltip

        def setProperty(self, _name: str, _value: str) -> None:
            pass

    qt_core = SimpleNamespace(
        Qt=SimpleNamespace(
            ToolButtonTextOnly="text-only",
            DownArrow="down",
            RightArrow="right",
        )
    )
    qt_widgets = SimpleNamespace(
        QWidget=_Widget,
        QVBoxLayout=_Layout,
        QToolButton=_ToolButton,
    )
    content = _Widget()

    wrapper, toggle = make_disclosure(
        "Advanced settings", content, qt_core, qt_widgets, expanded=False
    )

    assert isinstance(wrapper, _Widget)
    assert toggle.text == "Advanced settings"
    assert toggle.checkable is True
    assert toggle.checked is False
    assert toggle.arrow == "right"
    assert content.visible is False
    assert toggle.tooltip == "Show or hide optional advanced settings."

    toggle.setChecked(True)
    assert content.visible is True
    assert toggle.arrow == "down"

    toggle.setChecked(False)
    assert content.visible is False
    assert toggle.arrow == "right"

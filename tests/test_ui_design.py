# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the Qt UI design helpers that do not require a FreeCAD runtime."""

from collections.abc import Callable
from types import SimpleNamespace

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
        """Initialize an empty style-event recorder."""
        self.events: list[tuple[str, object]] = []

    def unpolish(self, widget: object) -> None:
        """Record a widget entering the style-unpolish phase."""

        Args:
            widget: Widget whose old style state is being cleared.
        self.events.append(("unpolish", widget))

    def polish(self, widget: object) -> None:
        """Record a widget entering the style-polish phase."""

        Args:
            widget: Widget receiving the refreshed style state.
        self.events.append(("polish", widget))


class _Label:
    """Minimal status-label stub for behavior that is independent of Qt."""

    def __init__(self) -> None:
        """Initialize the status label's observable state and style stub."""
        self.text: str = ""
        self.properties: dict[str, str] = {}
        self.wrap: bool = False
        self.events: list[str] = []
        self._style: _Style = _Style()

    def setText(self, value: str) -> None:
        """Store the visible status text for later assertions."""

        Args:
            value: Text assigned to the label.
        self.text = value

    def setWordWrap(self, value: bool) -> None:
        """Store whether status text should wrap across lines."""

        Args:
            value: Whether the label wraps its text.
        self.wrap = value

    def setProperty(self, name: str, value: str) -> None:
        """Store a dynamic property on the label stub."""

        Args:
            name: Dynamic property key to update.
            value: String value assigned to that property.
        self.properties[name] = value

    def style(self) -> _Style:
        """Return the style stub used to record refresh events."""

        Returns:
            Style stub associated with this label.
        return self._style

    def update(self) -> None:
        """Record a repaint request made by the status helper."""
        self.events.append("update")


def test_set_status_sets_text_semantic_state_and_wrap() -> None:
    """Check text, semantic state, wrapping, and style refresh behavior."""
    label = _Label()

    set_status(label, "Select two edges, then Preview.", state="warning")

    assert label.text == "Select two edges, then Preview."
    assert label.wrap is True
    assert label.properties == {"clothRole": "status", "clothState": "warning"}
    assert [event[0] for event in label._style.events] == ["unpolish", "polish"]
    assert label.events == ["update"]


def test_set_status_falls_back_to_info_for_unknown_states() -> None:
    """Use the informational state for an unrecognized status value."""
    label = _Label()

    set_status(label, "Ready", state="unexpected")

    assert label.properties["clothState"] == "info"


def test_mark_button_assigns_role_and_refreshes_style() -> None:
    """Assign the requested emphasis role and refresh the button style."""
    class _Button(_Label):
        pass

    button = _Button()
    mark_button(button, "primary")

    assert button.properties["clothEmphasis"] == "primary"
    assert [event[0] for event in button._style.events] == ["unpolish", "polish"]


def test_apply_panel_style_scopes_stylesheet_and_normalizes_layouts() -> None:
    """Scope the panel stylesheet and normalize outer and nested layouts."""
    class _QtLayout:
        pass

    class _Layout:
        def __init__(self) -> None:
            """Initialize layout state used by panel-style contract checks."""
            self.margins: tuple[int, int, int, int] | None = None
            self.spacing: int | None = None

        def setContentsMargins(self, left: int, top: int, right: int, bottom: int) -> None:
            """Record the four layout margins supplied by the styling helper."""

            Args:
                left: Margin measured from the left edge.
                top: Margin measured from the top edge.
                right: Margin measured from the right edge.
                bottom: Margin measured from the bottom edge.
            self.margins = (left, top, right, bottom)

        def setSpacing(self, spacing: int) -> None:
            """Record the spacing value applied to a layout."""

            Args:
                spacing: Distance used between layout items.
            self.spacing = spacing

    class _Panel:
        def __init__(self) -> None:
            """Initialize the panel stub and its outer and nested layouts."""
            self.stylesheet = ""
            self.outer_layout = _Layout()
            self.nested_layouts = [_Layout()]
            self.requested_child_type: type[object] | None = None

        def setStyleSheet(self, stylesheet: str) -> None:
            """Store the stylesheet assigned to this panel stub."""

            Args:
                stylesheet: Scoped stylesheet string applied to the panel.
            self.stylesheet = stylesheet

        def layout(self) -> _Layout:
            """Return the panel's outer layout for normalization checks."""

            Returns:
                Outer layout stub owned by this panel.
            return self.outer_layout

        def findChildren(self, widget_type: type[object]) -> list[_Layout]:
            """Return nested layouts matching the requested widget type."""

            Args:
                widget_type: Qt child type requested by the style helper.

            Returns:
                Nested layout stubs discovered for the requested type.
            self.requested_child_type = widget_type
            return self.nested_layouts

    panel = _Panel()
    apply_panel_style(panel, layout_type=_QtLayout)

    assert panel.stylesheet == PANEL_STYLE
    assert panel.outer_layout.margins == (8, 8, 8, 8)
    assert panel.outer_layout.spacing == 6
    assert panel.requested_child_type is _QtLayout
    assert panel.nested_layouts[0].spacing == 6


def test_make_disclosure_toggles_content_and_arrow() -> None:
    """Check that expanding and collapsing the disclosure updates its controls."""
    class _Signal:
        def __init__(self) -> None:
            """Initialize the signal with no connected callback."""
            self.callback: Callable[[bool], None] | None = None

        def connect(self, callback: Callable[[bool], None]) -> None:
            """Register the callback invoked when the signal emits a value."""

            Args:
                callback: Function called with the emitted checked state.
            self.callback = callback

        def emit(self, value: bool) -> None:
            """Invoke the registered callback when one is connected."""

            Args:
                value: Boolean state forwarded to the callback.
            if self.callback is not None:
                self.callback(value)

    class _Widget:
        def __init__(self, *_args: object) -> None:
            """Initialize the test widget as not yet shown."""
            Args:
                *_args: Constructor arguments received from the parent helper.
            self.visible: bool | None = None

        def setVisible(self, visible: bool) -> None:
            """Store whether the content widget is currently visible."""

            Args:
                visible: Visibility state assigned to the widget.
            self.visible = visible

    class _Layout:
        def __init__(self, _parent: object) -> None:
            """Initialize layout geometry and child-widget records."""
            Args:
                _parent: Parent object supplied by the disclosure helper.
            self.margins: tuple[int, int, int, int] | None = None
            self.spacing: int | None = None
            self.widgets: list[object] = []

        def setContentsMargins(self, left: int, top: int, right: int, bottom: int) -> None:
            """Record all four margins applied to the disclosure layout."""

            Args:
                left: Margin measured from the left edge.
                top: Margin measured from the top edge.
                right: Margin measured from the right edge.
                bottom: Margin measured from the bottom edge.
            self.margins = (left, top, right, bottom)

        def setSpacing(self, spacing: int) -> None:
            """Record the spacing value applied to the disclosure layout."""

            Args:
                spacing: Distance used between layout items.
            self.spacing = spacing

        def addWidget(self, widget: object) -> None:
            """Record a widget added to the test layout."""

            Args:
                widget: Child widget appended to the layout.
            self.widgets.append(widget)

    class _ToolButton(_Widget):
        def __init__(self, parent: object | None = None) -> None:
            """Initialize toggle state and an isolated signal stub."""
            Args:
                parent: Optional parent object supplied to the widget constructor.
            super().__init__(parent)
            self.text = ""
            self.checkable = False
            self.checked = False
            self.arrow: object | None = None
            self.tooltip = ""
            self.style: object | None = None
            self.toggled = _Signal()

        def setText(self, text: str) -> None:
            """Store the disclosure caption shown on the toggle button."""

            Args:
                text: Caption displayed by the disclosure control.
            self.text = text

        def setCheckable(self, checkable: bool) -> None:
            """Store whether the toggle control supports checked state."""

            Args:
                checkable: Whether the button can be checked.
            self.checkable = checkable

        def setChecked(self, checked: bool) -> None:
            """Update checked state and notify listeners when it changes."""

            Args:
                checked: Requested checked state of the toggle button.
            checked = bool(checked)
            if checked != self.checked:
                self.checked = checked
                self.toggled.emit(checked)

        def setArrowType(self, arrow: object) -> None:
            """Store the arrow direction presented by the toggle button."""

            Args:
                arrow: Arrow value selected by the disclosure helper.
            self.arrow = arrow

        def setToolButtonStyle(self, style: object) -> None:
            """Store the text-and-icon presentation mode of the button."""

            Args:
                style: Button presentation mode selected by the helper.
            self.style = style

        def setToolTip(self, tooltip: str) -> None:
            """Store the help text displayed for the disclosure toggle."""

            Args:
                tooltip: Tooltip text assigned to the button.
            self.tooltip = tooltip

        def setProperty(self, _name: str, _value: str) -> None:
            """Accept the dynamic property update issued by the disclosure helper."""

            Args:
                _name: Dynamic property key supplied by the helper.
                _value: String value supplied with that key.
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

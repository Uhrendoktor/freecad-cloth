# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the Qt UI design helpers that do not require a FreeCAD runtime."""

from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from typing import cast

from tests.support.assertions import require

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
        """Record a widget entering the style-unpolish phase.

        Args:
            widget: Widget whose old style state is being cleared.
        """
        self.events.append(("unpolish", widget))

    def polish(self, widget: object) -> None:
        """Record a widget entering the style-polish phase.

        Args:
            widget: Widget receiving the refreshed style state.
        """
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
        setattr(self, "setText", self.set_text)
        setattr(self, "setWordWrap", self.set_word_wrap)
        setattr(self, "setProperty", self.set_property)

    def set_text(self, value: str) -> None:
        """Store the visible status text for later assertions.

        Args:
            value: Text assigned to the label.
        """
        self.text = value

    def set_word_wrap(self, value: object) -> None:
        """Store whether status text should wrap across lines.

        Args:
            value: Whether the label wraps its text.
        """
        self.wrap = bool(value)

    def set_property(self, name: str, value: str) -> None:
        """Store a dynamic property on the label stub.

        Args:
            name: Dynamic property key to update.
            value: String value assigned to that property.
        """
        self.properties[name] = value

    def style(self) -> _Style:
        """Return the style stub used to record refresh events.

        Returns:
            Style stub associated with this label.
        """
        return self._style

    def update(self) -> None:
        """Record a repaint request made by the status helper."""
        self.events.append("update")


def test_set_status_sets_text_semantic_state_and_wrap() -> None:
    """Check text, semantic state, wrapping, and style refresh behavior."""
    label = _Label()

    cast(Callable[..., None], set_status)(label, "Select two edges, then Preview.", state="warning")

    require(
        condition=(label.text == "Select two edges, then Preview."),
        message="Status text should match the user-facing message.",
    )
    require(
        condition=(label.wrap is True),
        message="Status text should be configured to wrap.",
    )
    require(
        condition=(label.properties == {"clothRole": "status", "clothState": "warning"}),
        message="Status role and semantic state should be assigned.",
    )
    require(
        condition=([event[0] for event in label._style.events] == ["unpolish", "polish"]),
        message="The UI design helper did not preserve the expected contract.",
    )
    require(
        condition=(label.events == ["update"]),
        message="Status updates should request a repaint.",
    )


def test_set_status_falls_back_to_info_for_unknown_states() -> None:
    """Use the informational state for an unrecognized status value."""
    label = _Label()

    cast(Callable[..., None], set_status)(label, "Ready", state="unexpected")

    require(
        condition=(label.properties["clothState"] == "info"),
        message="Unknown status values should use the informational state.",
    )


def test_mark_button_assigns_role_and_refreshes_style() -> None:
    """Assign the requested emphasis role and refresh the button style."""

    class _Button(_Label):
        """Button stub reusing the status label's style-property behavior."""

    button = _Button()
    cast(Callable[..., None], mark_button)(button, "primary")

    require(
        condition=(button.properties["clothEmphasis"] == "primary"),
        message="The button should be assigned the requested emphasis role.",
    )
    require(
        condition=([event[0] for event in button._style.events] == ["unpolish", "polish"]),
        message="The UI design helper did not preserve the expected contract.",
    )


def test_apply_panel_style_scopes_stylesheet_and_normalizes_layouts() -> None:
    """Scope the panel stylesheet and normalize outer and nested layouts."""

    class _QtLayout:
        """Marker class representing the host Qt layout type."""

    class _Layout:
        """Layout stub that records margin and spacing updates."""

        def __init__(self) -> None:
            """Initialize layout state used by panel-style contract checks."""
            self.margins: tuple[int, int, int, int] | None = None
            self.spacing: int | None = None
            setattr(self, "setContentsMargins", self.set_contents_margins)
            setattr(self, "setSpacing", self.set_spacing)

        def set_contents_margins(self, left: int, top: int, right: int, bottom: int) -> None:
            """Record the four layout margins supplied by the styling helper.

            Args:
                left: Margin measured from the left edge.
                top: Margin measured from the top edge.
                right: Margin measured from the right edge.
                bottom: Margin measured from the bottom edge.
            """
            self.margins = (left, top, right, bottom)

        def set_spacing(self, spacing: int) -> None:
            """Record the spacing value applied to a layout.

            Args:
                spacing: Distance used between layout items.
            """
            self.spacing = spacing

    class _Panel:
        """Panel stub used to test canonical stylesheet and layout settings."""

        def __init__(self) -> None:
            """Initialize the panel stub and its outer and nested layouts."""
            self.stylesheet = ""
            self.outer_layout = _Layout()
            self.nested_layouts = [_Layout()]
            self.requested_child_type: type[object] | None = None
            setattr(self, "setStyleSheet", self.set_style_sheet)
            setattr(self, "findChildren", self.find_children)

        def set_style_sheet(self, stylesheet: str) -> None:
            """Store the stylesheet assigned to this panel stub.

            Args:
                stylesheet: Scoped stylesheet string applied to the panel.
            """
            self.stylesheet = stylesheet

        def layout(self) -> _Layout:
            """Return the panel's outer layout for normalization checks.

            Returns:
                Outer layout stub owned by this panel.
            """
            return self.outer_layout

        def find_children(self, widget_type: type[object]) -> list[_Layout]:
            """Return nested layouts matching the requested widget type.

            Args:
                widget_type: Qt child type requested by the style helper.

            Returns:
                Nested layout stubs discovered for the requested type.
            """
            self.requested_child_type = widget_type
            return self.nested_layouts

    panel = _Panel()
    cast(Callable[..., None], apply_panel_style)(panel, layout_type=_QtLayout)

    require(
        condition=(panel.stylesheet == PANEL_STYLE),
        message="The panel should receive the canonical stylesheet.",
    )
    require(
        condition=(panel.outer_layout.margins == (8, 8, 8, 8)),
        message="The outer layout should use canonical margins.",
    )
    require(
        condition=(panel.outer_layout.spacing == 6),
        message="The outer layout should use canonical spacing.",
    )
    require(
        condition=(panel.requested_child_type is _QtLayout),
        message="Nested layout lookup should use the supplied Qt layout type.",
    )
    require(
        condition=(panel.nested_layouts[0].spacing == 6),
        message="Nested layouts should use canonical spacing.",
    )


def test_make_disclosure_toggles_content_and_arrow() -> None:
    """Check that expanding and collapsing the disclosure updates its controls."""

    class _Signal:
        """Signal stub that stores and emits its connected callback."""

        def __init__(self) -> None:
            """Initialize the signal with no connected callback."""
            self.callback: Callable[[bool], None] | None = None

        def connect(self, callback: Callable[[bool], None]) -> None:
            """Register the callback invoked when the signal emits a value.

            Args:
                callback: Function called with the emitted checked state.
            """
            self.callback = callback

        def emit(self, value: object) -> None:
            """Invoke the registered callback when one is connected.

            Args:
                value: Boolean state forwarded to the callback.
            """
            if self.callback is not None:
                self.callback(bool(value))

    class _Widget:
        """Widget stub that tracks visibility for disclosure-content tests."""

        def __init__(self, *_args: object) -> None:
            """Initialize the test widget as not yet shown.

            Args:
                *_args: Constructor arguments received from the parent helper.
            """
            self.visible: bool | None = None
            setattr(self, "setVisible", self.set_visible)

        def set_visible(self, visible: object) -> None:
            """Store whether the content widget is currently visible.

            Args:
                visible: Visibility state assigned to the widget.
            """
            self.visible = bool(visible)

    class _Layout:
        """Layout stub that records disclosure geometry and child widgets."""

        def __init__(self, _parent: object) -> None:
            """Initialize layout geometry and child-widget records.

            Args:
                _parent: Parent object supplied by the disclosure helper.
            """
            self.margins: tuple[int, int, int, int] | None = None
            self.spacing: int | None = None
            self.widgets: list[object] = []
            setattr(self, "setContentsMargins", self.set_contents_margins)
            setattr(self, "setSpacing", self.set_spacing)
            setattr(self, "addWidget", self.add_widget)

        def set_contents_margins(self, left: int, top: int, right: int, bottom: int) -> None:
            """Record all four margins applied to the disclosure layout.

            Args:
                left: Margin measured from the left edge.
                top: Margin measured from the top edge.
                right: Margin measured from the right edge.
                bottom: Margin measured from the bottom edge.
            """
            self.margins = (left, top, right, bottom)

        def setSpacing(self, spacing: int) -> None:
            """Record the spacing value applied to the disclosure layout.

            Args:
                spacing: Distance used between layout items.
            """
            self.spacing = spacing

        def add_widget(self, widget: object) -> None:
            """Record a widget added to the test layout.

            Args:
                widget: Child widget appended to the layout.
            """
            self.widgets.append(widget)

    class _ToolButton(_Widget):
        """Button stub that records disclosure state and emitted toggles."""

        def __init__(self, parent: object | None = None) -> None:
            """Initialize toggle state and an isolated signal stub.
            Args:
                parent: Optional parent object supplied to the widget constructor.
            """
            super().__init__(parent)
            self.text = ""
            self.checkable = False
            self.checked = False
            self.arrow: object | None = None
            self.tooltip = ""
            self.style: object | None = None
            self.toggled = _Signal()
            setattr(self, "setText", self.set_text)
            setattr(self, "setCheckable", self.set_checkable)
            setattr(self, "setChecked", self.set_checked)
            setattr(self, "setArrowType", self.set_arrow_type)
            setattr(self, "setToolButtonStyle", self.set_tool_button_style)
            setattr(self, "setToolTip", self.set_tool_tip)
            setattr(self, "setProperty", self.set_property)

        def set_text(self, text: str) -> None:
            """Store the disclosure caption shown on the toggle button.

            Args:
                text: Caption displayed by the disclosure control.
            """
            self.text = text

        def set_checkable(self, checkable: object) -> None:
            """Store whether the toggle control supports checked state.

            Args:
                checkable: Whether the button can be checked.
            """
            self.checkable = bool(checkable)

        def set_checked(self, checked: object) -> None:
            """Update checked state and notify listeners when it changes.

            Args:
                checked: Requested checked state of the toggle button.
            """
            checked = bool(checked)
            if checked != self.checked:
                self.checked = checked
                self.toggled.emit(checked)

        def set_arrow_type(self, arrow: object) -> None:
            """Store the arrow direction presented by the toggle button.

            Args:
                arrow: Arrow value selected by the disclosure helper.
            """
            self.arrow = arrow

        def set_tool_button_style(self, style: object) -> None:
            """Store the text-and-icon presentation mode of the button.

            Args:
                style: Button presentation mode selected by the helper.
            """
            self.style = style

        def set_tool_tip(self, tooltip: str) -> None:
            """Store the help text displayed for the disclosure toggle.

            Args:
                tooltip: Tooltip text assigned to the button.
            """
            self.tooltip = tooltip

        @staticmethod
        def set_property(_name: str, _value: str) -> None:
            """Accept a dynamic property update sent to the disclosure toggle.

            Args:
                _name: Dynamic property key supplied by the helper.
                _value: String value supplied with that key.
            """
            pass

    qt_core = ModuleType("qt_core_stub")
    setattr(
        qt_core,
        "Qt",
        SimpleNamespace(
            ToolButtonTextOnly="text-only",
            DownArrow="down",
            RightArrow="right",
        ),
    )
    qt_widgets = ModuleType("qt_widgets_stub")
    setattr(qt_widgets, "QWidget", _Widget)
    setattr(qt_widgets, "QVBoxLayout", _Layout)
    setattr(qt_widgets, "QToolButton", _ToolButton)
    content = _Widget()

    disclosure_factory = cast(Callable[..., tuple[object, object]], make_disclosure)
    wrapper_value, toggle_value = disclosure_factory(
        "Advanced settings", content, qt_core, qt_widgets, expanded=False
    )
    wrapper = cast(_Widget, wrapper_value)
    toggle = cast(_ToolButton, toggle_value)

    require(
        condition=(isinstance(wrapper, _Widget)),
        message="The disclosure wrapper should be a widget.",
    )
    require(
        condition=(toggle.text == "Advanced settings"),
        message="The disclosure should expose its requested caption.",
    )
    require(
        condition=(toggle.checkable is True),
        message="The disclosure toggle should be checkable.",
    )
    require(
        condition=(toggle.checked is False),
        message="The disclosure toggle should start collapsed.",
    )
    require(
        condition=(toggle.arrow == "right"),
        message="The disclosure arrow should reflect its expanded or collapsed state.",
    )
    require(
        condition=(content.visible is False),
        message="Disclosure content visibility should follow toggle state.",
    )
    require(
        condition=(toggle.tooltip == "Show or hide optional advanced settings."),
        message="The disclosure should provide the expected tooltip.",
    )

    toggle.set_checked(True)
    require(
        condition=(content.visible is True),
        message="Disclosure content visibility should follow toggle state.",
    )
    require(
        condition=(toggle.arrow == "down"),
        message="The disclosure arrow should reflect its expanded or collapsed state.",
    )

    toggle.set_checked(False)
    require(
        condition=(content.visible is False),
        message="Disclosure content visibility should follow toggle state.",
    )
    require(
        condition=(toggle.arrow == "right"),
        message="The disclosure arrow should reflect its expanded or collapsed state.",
    )

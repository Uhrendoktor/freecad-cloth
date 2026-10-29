# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the Qt UI design helpers that do not require a FreeCAD runtime."""

from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from typing import ClassVar, cast

from freecad_cloth.common.UiDesign import (
    PANEL_STYLE,
    apply_panel_style,
    make_disclosure,
    mark_button,
    set_status,
)

from tests.support.assertions import require


class _QtMethodAdapter:
    """Resolve selected Qt camelCase calls to snake_case test-double methods."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {}

    def __getattr__(self, name: str) -> object:
        """Resolve a declared host API alias to its test-double implementation.

        Args:
            name: Dynamic attribute requested by the helper under test.

        Returns:
            Bound test-double method corresponding to the declared Qt alias.

        Raises:
            AttributeError: If the requested name is not a declared Qt alias.
        """
        method_name = self._qt_method_aliases.get(name)
        if method_name is None:
            raise AttributeError(name)
        return getattr(self, method_name)


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


class _Label(_QtMethodAdapter):
    """Minimal status-label stub for behavior that is independent of Qt."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {
        "setText": "set_text",
        "setWordWrap": "set_word_wrap",
        "setProperty": "set_property",
    }

    def __init__(self) -> None:
        """Initialize the status label's observable state and style stub."""
        self.text: str = ""
        self.properties: dict[str, str] = {}
        self.wrap: bool = False
        self.events: list[str] = []
        self._style: _Style = _Style()

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

    @property
    def style_events(self) -> list[tuple[str, object]]:
        """Return ordered style-refresh events for public test assertions.

        Returns:
            Recorded style operation names and associated widget objects.
        """
        return self._style.events


class _Button(_Label):
    """Button stub reusing the status label's style-property behavior."""


class _QtLayout:
    """Marker class representing the host Qt layout type."""


class _PanelLayout(_QtMethodAdapter):
    """Layout stub recording panel margin and spacing updates."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {
        "setContentsMargins": "set_contents_margins",
        "setSpacing": "set_spacing",
    }

    def __init__(self) -> None:
        """Initialize empty layout measurements."""
        self.margins: tuple[int, int, int, int] | None = None
        self.spacing: int | None = None

    def set_contents_margins(self, left: int, top: int, right: int, bottom: int) -> None:
        """Record the four margins supplied by the panel-style helper.

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


class _Panel(_QtMethodAdapter):
    """Panel stub used to test canonical stylesheet and layout settings."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {
        "setStyleSheet": "set_style_sheet",
        "findChildren": "find_children",
    }

    def __init__(self) -> None:
        """Initialize a panel with outer and nested layout stubs."""
        self.stylesheet = ""
        self.outer_layout = _PanelLayout()
        self.nested_layouts = [_PanelLayout()]
        self.requested_child_type: type[object] | None = None

    def set_style_sheet(self, stylesheet: str) -> None:
        """Store the stylesheet assigned to this panel stub.

        Args:
            stylesheet: Scoped stylesheet string applied to the panel.
        """
        self.stylesheet = stylesheet

    def layout(self) -> _PanelLayout:
        """Return the panel's outer layout for normalization checks.

        Returns:
            Outer layout stub owned by this panel.
        """
        return self.outer_layout

    def find_children(self, widget_type: type[object]) -> list[_PanelLayout]:
        """Return nested layouts matching the requested widget type.

        Args:
            widget_type: Qt child type requested by the style helper.

        Returns:
            Nested layout stubs discovered for the requested type.
        """
        self.requested_child_type = widget_type
        return self.nested_layouts


class _Signal:
    """Signal stub storing one callback and forwarding emitted state values."""

    def __init__(self) -> None:
        """Initialize the signal without a registered callback."""
        self.callback: Callable[[bool], None] | None = None

    def connect(self, callback: Callable[[bool], None]) -> None:
        """Register the callback to receive emitted state values.

        Args:
            callback: Function invoked when the signal emits a state.
        """
        self.callback = callback

    def emit(self, value: object) -> None:
        """Invoke the callback with the boolean form of an emitted value.

        Args:
            value: Value forwarded by the test signal.
        """
        if self.callback is not None:
            self.callback(bool(value))


class _DisclosureWidget(_QtMethodAdapter):
    """Widget stub that tracks disclosure-content visibility."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {"setVisible": "set_visible"}

    def __init__(self, *_args: object) -> None:
        """Initialize a widget as not yet visible.

        Args:
            *_args: Constructor arguments received from the parent helper.
        """
        self.visible: bool | None = None

    def set_visible(self, visible: object) -> None:
        """Record the visibility state assigned to the widget.

        Args:
            visible: Visibility state assigned by the disclosure helper.
        """
        self.visible = bool(visible)


class _DisclosureLayout(_QtMethodAdapter):
    """Layout stub that records disclosure geometry and child widgets."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {
        "setContentsMargins": "set_contents_margins",
        "setSpacing": "set_spacing",
        "addWidget": "add_widget",
    }

    def __init__(self, _parent: object) -> None:
        """Initialize disclosure layout measurements and child records.

        Args:
            _parent: Parent object supplied by the disclosure helper.
        """
        self.margins: tuple[int, int, int, int] | None = None
        self.spacing: int | None = None
        self.widgets: list[object] = []

    def set_contents_margins(self, left: int, top: int, right: int, bottom: int) -> None:
        """Record all four margins applied to the disclosure layout.

        Args:
            left: Margin measured from the left edge.
            top: Margin measured from the top edge.
            right: Margin measured from the right edge.
            bottom: Margin measured from the bottom edge.
        """
        self.margins = (left, top, right, bottom)

    def set_spacing(self, spacing: int) -> None:
        """Record the spacing value applied to the disclosure layout.

        Args:
            spacing: Distance used between layout items.
        """
        self.spacing = spacing

    def add_widget(self, widget: object) -> None:
        """Record a child widget added to the disclosure layout.

        Args:
            widget: Child widget appended to the layout.
        """
        self.widgets.append(widget)


class _ToolButton(_DisclosureWidget):
    """Button stub recording disclosure state and emitted toggles."""

    _qt_method_aliases: ClassVar[dict[str, str]] = {
        "setVisible": "set_visible",
        "setText": "set_text",
        "setCheckable": "set_checkable",
        "setChecked": "set_checked",
        "setArrowType": "set_arrow_type",
        "setToolButtonStyle": "set_tool_button_style",
        "setToolTip": "set_tool_tip",
        "setProperty": "set_property",
    }

    def __init__(self, parent: object | None = None) -> None:
        """Initialize toggle state and its isolated signal stub.

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
        self.properties: dict[str, str] = {}
        self.toggled = _Signal()

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

    def set_property(self, name: str, value: str) -> None:
        """Record the dynamic property update sent to the disclosure toggle.

        Args:
            name: Dynamic property key supplied by the helper.
            value: String value supplied with that key.
        """
        self.properties[name] = value


EXPECTED_LAYOUT_SPACING = 6


def test_set_status_sets_text_semantic_state_and_wrap() -> None:
    """Check text, semantic state, wrapping, and style refresh behavior."""
    label = _Label()
    status_setter = cast("Callable[..., None]", set_status)

    status_setter(label, "Select two edges, then Preview.", state="warning")

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
        condition=([event[0] for event in label.style_events] == ["unpolish", "polish"]),
        message="The UI design helper did not preserve the expected contract.",
    )
    require(
        condition=(label.events == ["update"]),
        message="Status updates should request a repaint.",
    )


def test_set_status_falls_back_to_info_for_unknown_states() -> None:
    """Use the informational state for an unrecognized status value."""
    label = _Label()
    status_setter = cast(Callable[..., None], set_status)

    status_setter(label, "Ready", state="unexpected")

    require(
        condition=(label.properties["clothState"] == "info"),
        message="Unknown status values should use the informational state.",
    )


def test_mark_button_assigns_role_and_refreshes_style() -> None:
    """Assign the requested emphasis role and refresh the button style."""

    button = _Button()
    cast("Callable[..., None]", mark_button)(button, "primary")

    require(
        condition=(button.properties["clothEmphasis"] == "primary"),
        message="The button should be assigned the requested emphasis role.",
    )
    require(
        condition=([event[0] for event in button.style_events] == ["unpolish", "polish"]),
        message="The UI design helper did not preserve the expected contract.",
    )


def test_apply_panel_style_scopes_stylesheet_and_normalizes_layouts() -> None:
    """Scope the panel stylesheet and normalize outer and nested layouts."""

    panel = _Panel()
    cast("Callable[..., None]", apply_panel_style)(panel, layout_type=_QtLayout)

    require(
        condition=(panel.stylesheet == PANEL_STYLE),
        message="The panel should receive the canonical stylesheet.",
    )
    require(
        condition=(panel.outer_layout.margins == (8, 8, 8, 8)),
        message="The outer layout should use canonical margins.",
    )
    require(
        condition=(panel.outer_layout.spacing == EXPECTED_LAYOUT_SPACING),
        message="The outer layout should use canonical spacing.",
    )
    require(
        condition=(panel.requested_child_type is _QtLayout),
        message="Nested layout lookup should use the supplied Qt layout type.",
    )
    require(
        condition=(panel.nested_layouts[0].spacing == EXPECTED_LAYOUT_SPACING),
        message="Nested layouts should use canonical spacing.",
    )


def test_make_disclosure_toggles_content_and_arrow() -> None:
    """Check that expanding and collapsing disclosure updates its controls."""
    qt_core = cast(
        "ModuleType",
        SimpleNamespace(
            Qt=SimpleNamespace(
                ToolButtonTextOnly="text-only",
                DownArrow="down",
                RightArrow="right",
            )
        ),
    )
    qt_widgets = cast(
        "ModuleType",
        SimpleNamespace(
            QWidget=_DisclosureWidget,
            QVBoxLayout=_DisclosureLayout,
            QToolButton=_ToolButton,
        ),
    )
    content = _DisclosureWidget()
    disclosure_factory = cast("Callable[..., tuple[object, object]]", make_disclosure)
    wrapper_value, toggle_value = disclosure_factory(
        "Advanced settings", content, qt_core, qt_widgets, expanded=False
    )
    wrapper = cast("_DisclosureWidget", wrapper_value)
    toggle = cast("_ToolButton", toggle_value)

    require(
        condition=isinstance(wrapper, _DisclosureWidget),
        message="The disclosure wrapper should be a widget.",
    )
    require(
        condition=toggle.text == "Advanced settings",
        message="The disclosure should expose its requested caption.",
    )
    require(
        condition=toggle.checkable is True,
        message="The disclosure toggle should be checkable.",
    )
    require(
        condition=toggle.checked is False,
        message="The disclosure toggle should start collapsed.",
    )
    require(
        condition=toggle.arrow == "right",
        message="The disclosure arrow should reflect its expanded or collapsed state.",
    )
    require(
        condition=content.visible is False,
        message="Disclosure content visibility should follow toggle state.",
    )
    require(
        condition=toggle.tooltip == "Show or hide optional advanced settings.",
        message="The disclosure should provide the expected tooltip.",
    )

    toggle.set_checked(True)
    require(
        condition=content.visible is True,
        message="Disclosure content visibility should follow toggle state.",
    )
    require(
        condition=toggle.arrow == "down",
        message="The disclosure arrow should reflect its expanded or collapsed state.",
    )

    toggle.set_checked(False)
    require(
        condition=content.visible is False,
        message="Disclosure content visibility should follow toggle state.",
    )
    require(
        condition=toggle.arrow == "right",
        message="The disclosure arrow should reflect its expanded or collapsed state.",
    )

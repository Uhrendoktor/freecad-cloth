"""Shared, restrained UI conventions for Cloth Qt task panels.

The helpers only style the supplied panel and its descendants. They never
change FreeCAD's application-wide style or palette, and they do not own any
feature-domain behavior.
"""

from types import ModuleType
from typing import Protocol, cast


class _Style(Protocol):
    """Minimal Qt style operations needed to refresh dynamic properties."""

    def unpolish(self, widget: object) -> object: ...

    def polish(self, widget: object) -> object: ...


class _StyledWidget(Protocol):
    """Small structural contract shared by styled Qt widgets."""

    def style(self) -> _Style | None: ...

    def setProperty(self, _name: str, _value: str) -> object: ...

    def update(self) -> object: ...


class _StatusLabel(_StyledWidget, Protocol):
    """Qt label capabilities needed to present status feedback."""

    def setText(self, text: str) -> object: ...

    def setWordWrap(self, _enabled: bool) -> object: ...


class _Layout(Protocol):
    """Layout operations used to normalize task-panel spacing."""

    def setContentsMargins(self, _left: int, _top: int, _right: int, _bottom: int) -> object: ...

    def setSpacing(self, _spacing: int) -> object: ...


class _Panel(_StyledWidget, Protocol):
    """Qt root-widget contract used by panel-local styling."""

    def setStyleSheet(self, _style_sheet: str) -> object: ...

    def layout(self) -> _Layout | None: ...

    def findChildren(self, _widget_type: type[object]) -> list[_Layout]: ...


class _VisibilityWidget(Protocol):
    """Widget capability required by an expandable settings disclosure."""

    def setVisible(self, _visible: bool) -> object: ...


PANEL_STYLE = r"""
QGroupBox {
    font-weight: 600;
    margin-top: 7px;
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 5px 6px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 6px;
    padding: 0 3px;
}
QLabel[clothRole="title"] {
    font-weight: 600;
}
QLabel[clothRole="subtitle"] {
    font-weight: 600;
}
QLabel[clothRole="hint"] {
    color: palette(mid);
}
QLabel[clothRole="status"] {
    padding: 5px 7px;
    border: 1px solid palette(mid);
    border-left: 3px solid palette(highlight);
    border-radius: 3px;
    background: palette(alternate-base);
}
QLabel[clothRole="status"][clothState="warning"] {
    font-weight: 600;
    border-left-color: palette(link);
}
QLabel[clothRole="status"][clothState="error"] {
    font-weight: 600;
    border-left-color: palette(bright-text);
}
QLabel[clothRole="status"][clothState="success"] {
    border-left-color: palette(highlight);
}
QPushButton[clothEmphasis="primary"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(highlight);
    padding: 4px 9px;
}
QPushButton[clothEmphasis="primary"]:disabled {
    color: palette(mid);
    background-color: palette(button);
    border-color: palette(mid);
}
QPushButton[clothEmphasis="danger"] {
    font-weight: 600;
    border: 1px solid palette(bright-text);
}
QPushButton[clothEmphasis="secondary"] {
    padding: 4px 8px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    padding: 2px 4px;
    border: 1px solid palette(mid);
    border-radius: 2px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid palette(highlight);
}
QCheckBox {
    spacing: 6px;
}
QPushButton:disabled, QToolButton:disabled {
    color: palette(mid);
}
"""


def _refresh_widget_style(widget: _StyledWidget) -> None:
    """Re-evaluate local style selectors after a dynamic property changes."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def apply_panel_style(panel: _Panel | None, *, layout_type: type[object] | None = None) -> None:
    """Apply restrained palette-aware styling to one panel and normalize spacing.

    The supplied widget is the styling boundary. This deliberately avoids
    QApplication.setStyleSheet so the host FreeCAD UI remains in control.
    """
    if panel is None:
        return
    panel.setStyleSheet(PANEL_STYLE)
    layout = panel.layout()
    if layout is not None:
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
    if layout_type is None:
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        layout_type = cast(type[object], QtWidgets.QLayout)
    for nested_layout in panel.findChildren(layout_type):
        nested_layout.setSpacing(6)


def mark_button(button: _StyledWidget | None, emphasis: str = "secondary") -> None:
    """Assign a semantic emphasis role to a task-panel button."""
    if button is None:
        return
    button.setProperty("clothEmphasis", str(emphasis))
    _refresh_widget_style(button)


def set_status(label: _StatusLabel | None, text: str, state: str = "info") -> None:
    """Set readable status text and one of info, warning, error or success states.

    State is communicated in text as well as styling by callers; color is never
    the only distinction. Dynamic properties preserve the current Qt palette.
    """
    if label is None:
        return
    label.setText(str(text))
    label.setWordWrap(True)
    label.setProperty("clothRole", "status")
    valid_states = {"info", "warning", "error", "success"}
    label.setProperty("clothState", state if state in valid_states else "info")
    _refresh_widget_style(label)


def make_disclosure(
    title: str,
    content: _VisibilityWidget,
    qt_core: ModuleType,
    qt_widgets: ModuleType,
    expanded: bool = False,
) -> tuple[object, object]:
    """Wrap optional settings in a compact, keyboard-operable disclosure row.

    Returns the wrapper widget and its checkable toggle so a panel may expose
    the toggle as an attribute for testing or contextual behavior.
    """
    wrapper = qt_widgets.QWidget()
    layout = qt_widgets.QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    toggle = qt_widgets.QToolButton(wrapper)
    toggle.setText(str(title))
    toggle.setCheckable(True)
    toggle.setToolButtonStyle(qt_core.Qt.ToolButtonTextOnly)
    toggle.setArrowType(qt_core.Qt.DownArrow if expanded else qt_core.Qt.RightArrow)
    toggle.setToolTip("Show or hide optional advanced settings.")
    toggle.setProperty("clothRole", "disclosure")
    layout.addWidget(toggle)
    layout.addWidget(content)

    def _toggle_content(checked: bool) -> None:
        content.setVisible(bool(checked))
        toggle.setArrowType(qt_core.Qt.DownArrow if checked else qt_core.Qt.RightArrow)

    toggle.toggled.connect(_toggle_content)
    content.setVisible(bool(expanded))
    toggle.setChecked(bool(expanded))
    return wrapper, toggle

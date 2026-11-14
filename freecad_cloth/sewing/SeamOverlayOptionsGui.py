# Copyright (C) 2026 FreeCAD Cloth contributors
"""Native FreeCAD task panel for seam-overlay display preferences."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets


def _gui_modules():
    """Load the FreeCAD GUI and Qt modules supported by the host runtime.

    Returns:
        FreeCAD GUI and QtWidgets modules in that order.
    """
    import FreeCADGui as Gui

    if TYPE_CHECKING:
        QtWidgets = _QT_TYPE_QtWidgets
    else:
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
    return Gui, QtWidgets


class SeamOverlayOptionsTaskPanel:
    """Stage seam overlay preferences in the active FreeCAD task panel."""

    def __init__(self) -> None:
        """Build the compact display-options form inside FreeCAD's task-panel host."""
        _App, Gui, QtWidgets = _gui_modules()
        self.Gui = Gui
        from freecad_cloth.sewing.SeamOverlay import (
            seam_highlights_enabled,
            seam_overlay_respects_depth,
        )

        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothSeamOverlayOptionsTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        title = QtWidgets.QLabel("Seam overlay")
        title.setProperty("clothRole", "title")
        root.addWidget(title)

        display = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QVBoxLayout(display)
        self.highlights = QtWidgets.QCheckBox("Show seam color highlights")
        self.highlights.setChecked(seam_highlights_enabled())
        self.highlights.setToolTip(
            "Use seam identity colors, direction marks, and hover labels. "
            "Turn this off to show neutral seam linework."
        )
        display_layout.addWidget(self.highlights)

        self.respect_depth = QtWidgets.QCheckBox("Respect depth and occlusion")
        self.respect_depth.setChecked(seam_overlay_respects_depth())
        self.respect_depth.setToolTip(
            "Hide seam lines and labels when foreground geometry occludes them."
        )
        display_layout.addWidget(self.respect_depth)
        root.addWidget(display)

        explanation = QtWidgets.QLabel(
            "Seam labels appear only while the pointer is over a sewn pattern edge."
        )
        explanation.setWordWrap(True)
        explanation.setProperty("clothRole", "hint")
        root.addWidget(explanation)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        from freecad_cloth.common.UiDesign import apply_panel_style, set_status

        set_status(
            self.status,
            "Changes are staged. Choose OK to apply them, or Cancel to keep the current settings.",
            state="info",
        )
        root.addWidget(self.status)
        root.addStretch(1)
        apply_panel_style(self.form)

    def accept(self) -> bool:
        """Persist both staged display preferences when FreeCAD accepts the panel.

        Returns:
            True after the two overlay preferences have been saved.
        """
        from freecad_cloth.sewing.SeamOverlay import (
            set_seam_highlights_enabled,
            set_seam_overlay_respect_depth,
        )

        set_seam_highlights_enabled(self.highlights.isChecked())
        set_seam_overlay_respect_depth(self.respect_depth.isChecked())
        return True

    def reject(self) -> bool:
        """Discard uncommitted checkbox changes without changing saved preferences.

        Returns:
            True to allow FreeCAD to close the task panel.
        """
        return True

    def getStandardButtons(self) -> int:
        """Return FreeCAD's native OK and Cancel task-panel buttons.

        Returns:
            Combined Qt dialog-button flags for the host task-panel footer.
        """
        _App, _Gui, QtWidgets = _gui_modules()
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))


def show_seam_overlay_options_task() -> SeamOverlayOptionsTaskPanel:
    """Open seam-overlay preferences using the current FreeCAD task-panel host.

    Returns:
        The active seam-overlay task-panel instance.
    """
    _App, Gui, _QtWidgets = _gui_modules()
    panel = SeamOverlayOptionsTaskPanel()
    Gui.Control.showDialog(panel)
    return panel

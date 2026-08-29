"""FreeCAD task panel for editing sewing operations.

The module keeps all FreeCAD/Qt imports lazy so importing it from headless
Python tests does not require a GUI runtime.
"""


def _gui_modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


class SewingTaskPanel:
    """Task-panel editor following FreeCAD's accept/reject contract.

    Semantic seam settings are edited on the linked ``Seam`` object.  The
    sewing operation remains a derived document view, so the panel never
    creates a second source of truth for reversal/alignment.
    """

    def __init__(self, obj):
        App, Gui, QtCore, QtWidgets = _gui_modules()
        self.App = App
        self.Gui = Gui
        self.QtCore = QtCore
        self.obj = obj
        self.seam = getattr(obj, "Seam", None)
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)

        seam_id = str(getattr(self.seam, "SeamId", "")) if self.seam else ""
        piece_a = getattr(self.seam, "PieceA", None) if self.seam else None
        piece_b = getattr(self.seam, "PieceB", None) if self.seam else None
        self.seam_info = QtWidgets.QLabel(
            "%s: %s ↔ %s" % (seam_id or "Unassigned seam", piece_a or "?", piece_b or "?")
        )
        self.seam_info.setWordWrap(True)
        layout.addRow("Seam", self.seam_info)

        self.alignment = QtWidgets.QComboBox()
        self.alignment.addItems(["endpoints", "uniform"])
        current_alignment = str(getattr(self.seam, "Alignment", getattr(obj, "Alignment", "endpoints")))
        index = self.alignment.findText(current_alignment)
        self.alignment.setCurrentIndex(max(0, index))
        layout.addRow("Alignment", self.alignment)

        self.reversed_b = QtWidgets.QCheckBox("Reverse B correspondence")
        self.reversed_b.setChecked(bool(getattr(self.seam, "ReversedB", getattr(obj, "ReversedB", False))))
        layout.addRow("Orientation", self.reversed_b)

        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(0, 1000)
        self.tolerance.setDecimals(2)
        self.tolerance.setSuffix(" mm")
        self.tolerance.setValue(float(obj.Tolerance))
        layout.addRow("Validation tolerance", self.tolerance)

        self.stitches = QtWidgets.QSpinBox()
        self.stitches.setRange(2, 10000)
        self.stitches.setValue(max(2, int(obj.Stitches)))
        layout.addRow("Stitch samples", self.stitches)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.lengths = QtWidgets.QLabel()
        self.lengths.setWordWrap(True)
        layout.addRow("Status", self.status)
        layout.addRow("Seam lengths", self.lengths)

        self._original = {
            "Tolerance": float(obj.Tolerance),
            "Stitches": int(obj.Stitches),
            "Alignment": str(getattr(self.seam, "Alignment", "endpoints")) if self.seam else "endpoints",
            "ReversedB": bool(getattr(self.seam, "ReversedB", False)) if self.seam else False,
        }
        self._refresh()

    def _refresh(self):
        self.status.setText(str(self.obj.Status))
        self.lengths.setText(
            "%.2f / %.2f mm (Δ %.2f)"
            % (
                float(self.obj.LengthA),
                float(self.obj.LengthB),
                float(self.obj.LengthDifference),
            )
        )

    def update(self):
        """Refresh values shown by the task panel after an external recompute."""
        self._refresh()

    def _apply_seam_settings(self):
        if self.seam is None:
            return
        self.seam.Alignment = str(self.alignment.currentText())
        self.seam.ReversedB = bool(self.reversed_b.isChecked())

    def accept(self):
        """Commit editor values, recompute the document, and finish the task."""
        self._apply_seam_settings()
        self.obj.Tolerance = self.tolerance.value()
        self.obj.Stitches = self.stitches.value()
        self.App.ActiveDocument.recompute()
        self._refresh()
        return True

    def reject(self):
        """Restore the pre-edit state and recompute before closing the task."""
        if self.seam is not None:
            self.seam.Alignment = self._original["Alignment"]
            self.seam.ReversedB = self._original["ReversedB"]
        self.obj.Tolerance = self._original["Tolerance"]
        self.obj.Stitches = self._original["Stitches"]
        self.App.ActiveDocument.recompute()
        self._refresh()
        return True

    def getStandardButtons(self):
        """Return the native Qt OK/Cancel task-panel buttons."""
        _App, _Gui, _QtCore, QtWidgets = _gui_modules()
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))


def show_sewing_task(obj):
    """Open a sewing operation in FreeCAD's task panel and return the panel."""
    _App, Gui, _QtCore, _QtWidgets = _gui_modules()
    panel = SewingTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel

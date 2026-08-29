"""FreeCAD task panel for editing sewing operations.

The module keeps all FreeCAD/Qt imports lazy so importing it from headless
Python tests does not require a GUI runtime.
"""


def _gui_modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class SewingTaskPanel:
    """Task-panel adapter following FreeCAD's accept/reject contract."""

    def __init__(self, obj):
        App, Gui, QtWidgets = _gui_modules()
        self.App = App
        self.Gui = Gui
        self.obj = obj
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)

        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(0, 1000)
        self.tolerance.setDecimals(2)
        self.tolerance.setSuffix(" mm")
        self.tolerance.setValue(float(obj.Tolerance))

        self.stitches = QtWidgets.QSpinBox()
        self.stitches.setRange(2, 10000)
        self.stitches.setValue(max(2, int(obj.Stitches)))

        self.status = QtWidgets.QLabel()
        self.lengths = QtWidgets.QLabel()
        layout.addRow("Validation tolerance", self.tolerance)
        layout.addRow("Stitch samples", self.stitches)
        layout.addRow("Status", self.status)
        layout.addRow("Seam lengths", self.lengths)

        # Keep a document-state snapshot until the panel is accepted. This
        # makes Cancel/Reject a true no-op even after an edit/recompute cycle.
        self._original = {
            "Tolerance": float(obj.Tolerance),
            "Stitches": int(obj.Stitches),
        }
        self._refresh()

    def _refresh(self):
        """Refresh both editor widgets and derived validation labels."""
        self.tolerance.setValue(float(self.obj.Tolerance))
        self.stitches.setValue(max(2, int(self.obj.Stitches)))
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

    def _recompute(self):
        document = getattr(self.App, "ActiveDocument", None)
        if document is not None:
            document.recompute()

    def accept(self):
        """Commit editor values, recompute the document, and finish the task."""
        self.obj.Tolerance = self.tolerance.value()
        self.obj.Stitches = self.stitches.value()
        self._recompute()
        self._refresh()
        return True

    def reject(self):
        """Restore the pre-edit state and recompute before closing the task."""
        self.obj.Tolerance = self._original["Tolerance"]
        self.obj.Stitches = self._original["Stitches"]
        self._recompute()
        self._refresh()
        return True

    def getStandardButtons(self):
        """Return the native Qt OK/Cancel task-panel buttons."""
        _App, _Gui, QtWidgets = _gui_modules()
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))


def show_sewing_task(obj):
    """Open a sewing operation in FreeCAD's task panel and return the panel."""
    _App, Gui, _QtWidgets = _gui_modules()
    panel = SewingTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel

"""FreeCAD task panel for editing sewing operations."""


def _gui_modules():
    import FreeCAD as App, FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class SewingTaskPanel:
    """FreeCAD task-panel contract for a persisted SewingOperation.

    The panel edits only user-controlled validation/stitch settings.  Seam
    identity, orientation, alignment and stitch-group metadata remain derived
    from the linked canonical seam object.
    """
    def __init__(self, obj):
        App, Gui, QtWidgets = _gui_modules()
        self.App, self.Gui, self.obj = App, Gui, obj
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)
        self.tolerance = QtWidgets.QDoubleSpinBox(); self.tolerance.setRange(0, 1000); self.tolerance.setDecimals(2); self.tolerance.setSuffix(" mm")
        self.stitches = QtWidgets.QSpinBox(); self.stitches.setRange(2, 10000)
        self.alignment = QtWidgets.QLabel(str(getattr(obj, "Alignment", "endpoints")))
        self.reversal = QtWidgets.QLabel("Reversed B" if bool(getattr(obj, "ReversedB", False)) else "Normal B")
        self.group = QtWidgets.QLabel(str(getattr(obj, "StitchGroup", "")))
        self.status = QtWidgets.QLabel(); self.lengths = QtWidgets.QLabel()
        self._original = (float(obj.Tolerance), int(obj.Stitches))
        self.tolerance.setValue(self._original[0]); self.stitches.setValue(max(2, self._original[1]))
        layout.addRow("Validation tolerance", self.tolerance)
        layout.addRow("Stitch samples", self.stitches)
        layout.addRow("Alignment", self.alignment)
        layout.addRow("Orientation", self.reversal)
        layout.addRow("Stitch group", self.group)
        layout.addRow("Status", self.status)
        layout.addRow("Seam lengths", self.lengths)
        self._refresh()

    def _refresh(self):
        self.status.setText(str(self.obj.Status))
        self.lengths.setText("%.2f / %.2f mm (Δ %.2f)" % (float(self.obj.LengthA), float(self.obj.LengthB), float(self.obj.LengthDifference)))

    def _apply(self):
        self.obj.Tolerance = self.tolerance.value()
        self.obj.Stitches = self.stitches.value()
        self.App.ActiveDocument.recompute()
        self._refresh()

    def accept(self):
        self._apply()
        return True

    def reject(self):
        self.obj.Tolerance = self._original[0]
        self.obj.Stitches = self._original[1]
        self.App.ActiveDocument.recompute()
        return True

    def getStandardButtons(self):
        return int(0x00000400 | 0x00800000)

    def isAllowedAlterations(self):
        return False


def show_sewing_task(obj):
    _App, Gui, _QtWidgets = _gui_modules()
    panel = SewingTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel

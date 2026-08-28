"""FreeCAD task panel for editing sewing operations.

Imports FreeCAD GUI modules lazily so headless model/test imports remain safe.
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
    def __init__(self, obj):
        App, Gui, QtWidgets = _gui_modules()
        self.App, self.Gui, self.obj = App, Gui, obj
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(0.0, 1000.0)
        self.tolerance.setDecimals(2)
        self.tolerance.setSuffix(" mm")
        self.stitches = QtWidgets.QSpinBox()
        self.stitches.setRange(2, 10000)
        self.stitches.setValue(max(2, int(obj.Stitches)))
        self.status = QtWidgets.QLabel(str(obj.Status))
        self.lengths = QtWidgets.QLabel()
        self.tolerance.setValue(float(obj.Tolerance))
        layout.addRow("Validation tolerance", self.tolerance)
        layout.addRow("Stitch samples", self.stitches)
        layout.addRow("Status", self.status)
        layout.addRow("Seam lengths", self.lengths)
        self._refresh()

    def _refresh(self):
        self.status.setText(str(self.obj.Status))
        self.lengths.setText("%.2f mm / %.2f mm (Δ %.2f mm)" % (
            float(self.obj.LengthA), float(self.obj.LengthB), float(self.obj.LengthDifference)))

    def accept(self):
        self.obj.Tolerance = self.tolerance.value()
        self.obj.Stitches = self.stitches.value()
        self.App.ActiveDocument.recompute()
        self._refresh()
        return True

    def reject(self):
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


def show_sewing_task(obj):
    _App, Gui, _QtWidgets = _gui_modules()
    panel = SewingTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel

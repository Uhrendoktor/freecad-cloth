"""FreeCAD GUI helpers for the Cloth Pattern workbench.

GUI dependencies are imported lazily so the model remains usable from freecadcmd.
"""

def _gui_modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class PatternPieceTaskPanel:
    """Task panel for creating or editing a parametric pattern piece."""
    def __init__(self, obj=None):
        App, Gui, QtWidgets = _gui_modules()
        self.App, self.Gui, self.obj = App, Gui, obj
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)
        self.name = QtWidgets.QLineEdit()
        self.width = QtWidgets.QDoubleSpinBox(); self.width.setRange(0.1, 100000); self.width.setDecimals(2); self.width.setSuffix(" mm")
        self.height = QtWidgets.QDoubleSpinBox(); self.height.setRange(0.1, 100000); self.height.setDecimals(2); self.height.setSuffix(" mm")
        self.allowance = QtWidgets.QDoubleSpinBox(); self.allowance.setRange(0, 1000); self.allowance.setDecimals(2); self.allowance.setSuffix(" mm")
        self.grain = QtWidgets.QDoubleSpinBox(); self.grain.setRange(-360, 360); self.grain.setDecimals(1); self.grain.setSuffix(" deg")
        layout.addRow("Piece name", self.name)
        layout.addRow("Width", self.width)
        layout.addRow("Height", self.height)
        layout.addRow("Seam allowance", self.allowance)
        layout.addRow("Grainline angle", self.grain)
        layout.addRow(QtWidgets.QLabel("Changes are stored as native FreeCAD properties."))
        if obj is not None:
            self.name.setText(obj.Label)
            self.width.setValue(float(obj.Width)); self.height.setValue(float(obj.Height))
            self.allowance.setValue(float(obj.SeamAllowance)); self.grain.setValue(float(obj.GrainlineAngle))

    def _apply(self):
        if self.obj is None:
            from PatternCommands import create_pattern_piece_from_parameters
            self.obj = create_pattern_piece_from_parameters(self.name.text().strip() or "PatternPiece", self.width.value(), self.height.value(), self.allowance.value(), self.grain.value())
        else:
            self.obj.Width = self.width.value(); self.obj.Height = self.height.value()
            self.obj.SeamAllowance = self.allowance.value(); self.obj.GrainlineAngle = self.grain.value()
            if self.name.text().strip(): self.obj.Label = self.name.text().strip()
            self.App.ActiveDocument.recompute()
        self.Gui.activeDocument().activeView().viewTop()
        self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        self._apply(); return True

    def reject(self):
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


def show_pattern_piece_task(obj=None):
    _App, Gui, _QtWidgets = _gui_modules()
    panel = PatternPieceTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel


def show_pattern_view():
    _App, Gui, _QtWidgets = _gui_modules()
    if Gui.activeDocument():
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()

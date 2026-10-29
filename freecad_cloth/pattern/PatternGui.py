# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD GUI helpers for the Cloth Pattern workbench."""


def _gui_modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets
    return App, Gui, QtWidgets, QtGui, QtCore


def _is_sketch_authoritative(obj):
    """Return whether a PatternPiece's linked native Sketch owns its geometry."""
    return bool(
        obj is not None
        and str(getattr(obj, "GeometryAuthority", "")) == "Sketcher"
        and getattr(obj, "Sketch", None) is not None
    )


class PatternPieceTaskPanel:
    def __init__(self, obj=None):
        App, Gui, QtWidgets, _, _ = _gui_modules()
        self.App, self.Gui, self.obj = App, Gui, obj
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — Pattern Piece")
        layout = QtWidgets.QFormLayout(self.form)
        self.name = QtWidgets.QLineEdit()
        self.mode = QtWidgets.QComboBox()
        self._sketch_authoritative = _is_sketch_authoritative(obj)
        if self._sketch_authoritative:
            # A Sketch-authoritative piece must not present parameter-driven
            # geometry choices that would suggest the rectangle is editable.
            self.mode.addItem("Sketch")
            self.mode.setEnabled(False)
        else:
            self.mode.addItems(["Rectangle", "Custom"])
        self.width = QtWidgets.QDoubleSpinBox()
        self.width.setRange(0.1, 100000)
        self.width.setDecimals(2)
        self.width.setSuffix(" mm")
        self.height = QtWidgets.QDoubleSpinBox()
        self.height.setRange(0.1, 100000)
        self.height.setDecimals(2)
        self.height.setSuffix(" mm")
        self.width.setEnabled(not self._sketch_authoritative)
        self.height.setEnabled(not self._sketch_authoritative)
        self.allowance = QtWidgets.QDoubleSpinBox()
        self.allowance.setRange(0, 1000)
        self.allowance.setDecimals(2)
        self.allowance.setSuffix(" mm")
        self.grain = QtWidgets.QDoubleSpinBox()
        self.grain.setRange(-360, 360)
        self.grain.setDecimals(1)
        self.grain.setSuffix(" deg")
        for label, widget in (
            ("Piece name", self.name),
            ("Geometry source", self.mode),
            ("Width (derived)", self.width),
            ("Height (derived)", self.height),
            ("Seam allowance", self.allowance),
            ("Grainline angle", self.grain),
        ):
            layout.addRow(label, widget)
        self.edit_sketch = None
        if self._sketch_authoritative:
            self.edit_sketch = QtWidgets.QPushButton("Edit native Sketch…")
            self.edit_sketch.clicked.connect(self._edit_sketch)
            layout.addRow("Geometry editor", self.edit_sketch)
        self.mode.currentTextChanged.connect(self._mode_changed)
        if obj:
            self.name.setText(obj.Label)
            current_mode = (
                "Sketch"
                if self._sketch_authoritative
                else str(getattr(obj, "GeometryMode", "Rectangle"))
            )
            if self.mode.findText(current_mode) >= 0:
                self.mode.setCurrentText(current_mode)
            self.width.setValue(float(obj.Width))
            self.height.setValue(float(obj.Height))
            self.allowance.setValue(float(obj.SeamAllowance))
            self.grain.setValue(float(obj.GrainlineAngle))
            self._original = {
                "Label": obj.Label,
                "GeometryMode": str(getattr(obj, "GeometryMode", "Rectangle")),
                "Width": float(obj.Width),
                "Height": float(obj.Height),
                "SeamAllowance": float(obj.SeamAllowance),
                "GrainlineAngle": float(obj.GrainlineAngle),
            }
        else:
            self.mode.setCurrentText("Rectangle")
            self._original = None
        self._mode_changed(self.mode.currentText())

        from freecad_cloth.common.UiDesign import apply_panel_style, mark_button

        mark_button(self.edit_sketch, "secondary")
        apply_panel_style(self.form)

    def _edit_sketch(self):
        if not self._sketch_authoritative or self.obj is None:
            return
        sketch = getattr(self.obj, "Sketch", None)
        if sketch is None:
            msg = "pattern piece has no native Sketcher representation"
            raise ValueError(msg)
        active = self.Gui.activeDocument()
        if active is None:
            msg = "no active FreeCAD document"
            raise RuntimeError(msg)
        active.setEdit(sketch.Name)

    def _mode_changed(self, mode):
        if self._sketch_authoritative:
            self.width.setEnabled(False)
            self.height.setEnabled(False)
            return
        custom = mode == "Custom"
        self.width.setEnabled(not custom)
        self.height.setEnabled(not custom)

    def _validate(self):
        name = self.name.text().strip()
        if not name:
            msg = "pattern piece name must not be empty"
            raise ValueError(msg)
        if (
            not self._sketch_authoritative
            and self.mode.currentText() == "Rectangle"
            and (self.width.value() <= 0 or self.height.value() <= 0)
        ):
            msg = "pattern piece dimensions must be positive"
            raise ValueError(msg)
        if self.allowance.value() < 0:
            msg = "seam allowance cannot be negative"
            raise ValueError(msg)

    def _apply(self):
        self._validate()
        mode = self.mode.currentText()
        if self.obj is None:
            from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters

            self.obj = create_pattern_piece_from_parameters(
                self.name.text().strip() or "PatternPiece",
                self.width.value(),
                self.height.value(),
                self.allowance.value(),
                self.grain.value(),
            )
        if not self._sketch_authoritative:
            if mode == "Rectangle":
                self.obj.GeometryMode = "Rectangle"
                self.obj.Width = self.width.value()
                self.obj.Height = self.height.value()
            else:
                self.obj.GeometryMode = "Custom"
        else:
            # Geometry and dimensions remain owned by the linked Sketcher source.
            self.obj.GeometryMode = "Sketch"
        self.obj.SeamAllowance = self.allowance.value()
        self.obj.GrainlineAngle = self.grain.value()
        self.obj.Label = self.name.text().strip() or self.obj.Label
        self.App.ActiveDocument.recompute()
        self.Gui.activeDocument().activeView().viewTop()
        self.Gui.activeDocument().activeView().fitAll()

    def _restore(self):
        if self.obj is None or self._original is None:
            return
        for key, value in self._original.items():
            setattr(self.obj, key, value)
        self.App.ActiveDocument.recompute()

    def accept(self):
        self._apply()
        return True

    def reject(self):
        self._restore()
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


def show_pattern_piece_task(obj=None):
    _App, Gui, _QtWidgets, _, _ = _gui_modules()
    panel = PatternPieceTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel


def show_pattern_view():
    _App, Gui, _QtWidgets, _, _ = _gui_modules()
    if Gui.activeDocument():
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()

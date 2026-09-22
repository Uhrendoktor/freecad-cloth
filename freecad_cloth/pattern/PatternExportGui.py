"""FreeCAD GUI for deterministic production pattern export."""

from pathlib import Path


def _qt():
    import FreeCAD as App, FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


def _selected_piece(doc):
    import FreeCADGui as Gui
    return next(
        (obj for obj in Gui.Selection.getSelection() if getattr(obj, "PatternType", "") == "PatternPiece"),
        next((obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"), None),
    )


class PatternExportTaskPanel:
    def __init__(self, piece=None):
        App, Gui, QtWidgets = _qt()
        self.App, self.Gui = App, Gui
        self.piece = piece or _selected_piece(App.ActiveDocument)
        if self.piece is None:
            raise ValueError("create or select a pattern piece before exporting")
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — Production Export")
        layout = QtWidgets.QFormLayout(self.form)
        self.format = QtWidgets.QComboBox()
        self.format.addItems(("SVG", "DXF"))
        self.units = QtWidgets.QLineEdit("mm")
        self.curve_samples = QtWidgets.QSpinBox()
        self.curve_samples.setRange(2, 512)
        self.curve_samples.setValue(64)
        self.path = QtWidgets.QLineEdit()
        self.browse = QtWidgets.QPushButton("Browse…")
        self.browse.clicked.connect(self._browse)
        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(self.path)
        path_row.addWidget(self.browse)
        self.status = QtWidgets.QLabel(
            "Source: %s | Piece ID: %s | Export is derived/read-only" %
            (getattr(self.piece, "Label", self.piece.Name), getattr(self.piece, "PieceId", ""))
        )
        self.status.setWordWrap(True)
        layout.addRow("Format", self.format)
        layout.addRow("Units", self.units)
        layout.addRow("Curve samples", self.curve_samples)
        layout.addRow("Output", path_row)
        layout.addRow("Status", self.status)
        self.format.currentTextChanged.connect(self._format_changed)
        self._format_changed(self.format.currentText())

    def _format_changed(self, value):
        current = self.path.text().strip()
        if current:
            suffix = ".svg" if str(value).lower() == "svg" else ".dxf"
            if Path(current).suffix.lower() in {".svg", ".dxf"}:
                self.path.setText(str(Path(current).with_suffix(suffix)))

    def _browse(self):
        _, _, QtWidgets = _qt()
        suffix = "SVG (*.svg)" if self.format.currentText().lower() == "svg" else "DXF (*.dxf)"
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(self.form, "Export Cloth Pattern", "", suffix)
        if path:
            self.path.setText(path)

    def accept(self):
        path = self.path.text().strip()
        if not path:
            raise ValueError("choose an output path before exporting")
        from freecad_cloth.pattern.PatternExport import export_pattern_piece
        try:
            result = export_pattern_piece(
                self.piece,
                path,
                self.format.currentText(),
                units=self.units.text().strip(),
                curve_samples=int(self.curve_samples.value()),
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.setText("Export blocked: %s" % exc)
            return False
        metadata = result["metadata"]
        self.status.setText(
            "Exported %s | %s | edges=%d | seams=%d | scale=%s | read-only source" %
            (
                Path(path).name,
                result["format"].upper(),
                len(metadata.get("edge_ids", ())),
                len(metadata.get("seam_ids", ())),
                metadata.get("scale", 1.0),
            )
        )
        return True

    def reject(self):
        return True

    def getStandardButtons(self):
        _, _, QtWidgets = _qt()
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))


def show_pattern_export_task(piece=None):
    _, Gui, _ = _qt()
    panel = PatternExportTaskPanel(piece)
    Gui.Control.showDialog(panel)
    if hasattr(panel.form, "isVisible") and not panel.form.isVisible():
        panel.form.show()
    return panel

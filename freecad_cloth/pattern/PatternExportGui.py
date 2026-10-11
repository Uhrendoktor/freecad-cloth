"""FreeCAD GUI for deterministic production pattern export."""

from pathlib import Path


def _qt():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


def _selected_piece(doc):
    import FreeCADGui as Gui

    return next(
        (
            obj
            for obj in Gui.Selection.getSelection()
            if getattr(obj, "PatternType", "") == "PatternPiece"
        ),
        next(
            (obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"), None
        ),
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
        self.format.addItems(("SVG", "DXF", "PDF"))
        self.pdf_paper_size = QtWidgets.QComboBox()
        self.pdf_paper_size.addItems(("A4", "Letter"))
        self.pdf_overlap = QtWidgets.QDoubleSpinBox()
        self.pdf_overlap.setRange(8.0, 80.0)
        self.pdf_overlap.setDecimals(1)
        self.pdf_overlap.setSingleStep(1.0)
        self.pdf_overlap.setValue(10.0)
        self.pdf_overlap.setSuffix(" mm")
        self.units = QtWidgets.QLineEdit("mm")
        self.units.setReadOnly(True)
        self.units.setToolTip(
            "Pattern geometry is defined in millimetres. Unit conversion is not supported yet."
        )
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
            "Source: {} | Piece ID: {} | Export is derived/read-only".format(
                getattr(self.piece, "Label", self.piece.Name), getattr(self.piece, "PieceId", "")
            )
        )
        self.status.setWordWrap(True)
        layout.addRow("Format", self.format)
        layout.addRow("PDF paper size", self.pdf_paper_size)
        layout.addRow("PDF tile overlap", self.pdf_overlap)
        self._pdf_paper_label = layout.labelForField(self.pdf_paper_size)
        self._pdf_overlap_label = layout.labelForField(self.pdf_overlap)
        layout.addRow("Geometry unit (fixed)", self.units)
        layout.addRow("Curve samples", self.curve_samples)
        layout.addRow("Output", path_row)
        layout.addRow("Status", self.status)
        self.format.currentTextChanged.connect(self._format_changed)
        self._format_changed(self.format.currentText())

    def _format_changed(self, value):
        is_pdf = str(value).lower() == "pdf"
        self.pdf_paper_size.setVisible(is_pdf)
        self.pdf_overlap.setVisible(is_pdf)
        self._pdf_paper_label.setVisible(is_pdf)
        self._pdf_overlap_label.setVisible(is_pdf)
        current = self.path.text().strip()
        if current:
            suffix = {"svg": ".svg", "dxf": ".dxf", "pdf": ".pdf"}.get(str(value).lower(), ".svg")
            if Path(current).suffix.lower() in {".svg", ".dxf", ".pdf"}:
                self.path.setText(str(Path(current).with_suffix(suffix)))

    def _browse(self):
        _, _, QtWidgets = _qt()
        suffix = {
            "svg": "SVG (*.svg)",
            "dxf": "DXF (*.dxf)",
            "pdf": "PDF (*.pdf)",
        }[self.format.currentText().lower()]
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self.form, "Export Cloth Pattern", "", suffix
        )
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
                paper_size=self.pdf_paper_size.currentText(),
                overlap_mm=float(self.pdf_overlap.value()),
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.setText(f"Export blocked: {exc}")
            return False
        metadata = result["metadata"]
        self.status.setText(
            "Exported %s | %s | edges=%d | seams=%d | scale=%s | read-only source"
            % (
                Path(path).name,
                result["format"].upper(),
                len(metadata.get("edge_ids", ())),
                len(metadata.get("seam_ids", ())),
                metadata.get("scale", 1.0),
            )
        )
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog():
            self.Gui.Control.closeDialog()
        return True

    def reject(self):
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog():
            self.Gui.Control.closeDialog()
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

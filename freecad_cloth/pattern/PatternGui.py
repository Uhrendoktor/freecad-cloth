"""FreeCAD GUI helpers for the Cloth Pattern workbench."""


def _gui_modules():
    import FreeCAD as App, FreeCADGui as Gui
    try:
        from PySide import QtWidgets, QtGui, QtCore
    except ImportError:
        from PySide2 import QtWidgets, QtGui, QtCore
    return App, Gui, QtWidgets, QtGui, QtCore


def _is_sketch_authoritative(obj):
    """Return whether a PatternPiece's linked native Sketch owns its geometry."""
    return bool(
        obj is not None
        and str(getattr(obj, "GeometryAuthority", "")) == "Sketcher"
        and getattr(obj, "Sketch", None) is not None
    )


class PatternExportTaskPanel:
    """Public SVG/DXF production export task panel for one selected PatternPiece."""

    def __init__(self, obj=None):
        from pathlib import Path
        App, Gui, QtWidgets, _, _ = _gui_modules()
        self.App, self.Gui = App, Gui
        if obj is None:
            obj = next(
                (candidate for candidate in Gui.Selection.getSelection()
                 if getattr(candidate, "PatternType", "") == "PatternPiece"),
                None,
            )
        if obj is None:
            raise ValueError("select a pattern piece before exporting")
        self.obj = obj
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — Production Export")
        layout = QtWidgets.QFormLayout(self.form)

        self.source = QtWidgets.QLabel(
            "%s (%s)" % (str(getattr(obj, "Label", "PatternPiece")), str(getattr(obj, "PieceId", "")))
        )
        self.source.setWordWrap(True)
        layout.addRow("Source", self.source)

        self.output_prefix = QtWidgets.QLineEdit()
        document = getattr(obj, "Document", None)
        file_name = str(getattr(document, "FileName", "") or "").strip()
        default_dir = Path(file_name).expanduser().parent if file_name else Path.cwd()
        default_prefix = default_dir / (str(getattr(obj, "Label", "PatternPiece")) + "-export")
        self.output_prefix.setText(str(default_prefix))
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.output_prefix)
        row.addWidget(browse)
        wrapper = QtWidgets.QWidget()
        wrapper.setLayout(row)
        layout.addRow("Output prefix", wrapper)

        self.units = QtWidgets.QComboBox()
        self.units.addItems(["mm", "cm", "in"])
        layout.addRow("Output units", self.units)

        self.scale = QtWidgets.QDoubleSpinBox()
        self.scale.setRange(0.000001, 1000000.0)
        self.scale.setDecimals(6)
        self.scale.setSingleStep(0.1)
        self.scale.setValue(1.0)
        layout.addRow("Scale factor", self.scale)
        layout.addRow(
            "",
            QtWidgets.QLabel(
                "Scale is applied after the source geometry is resolved; output remains derived/read-only."
            ),
        )

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addRow("Validation", self.status)
        self._refresh_validation()

    def _browse(self):
        _, _, QtWidgets, _, _ = _gui_modules()
        current = str(self.output_prefix.text() or "")
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self.form, "Choose export directory", str(Path(current).expanduser().parent)
        )
        if directory:
            name = Path(current).name or str(getattr(self.obj, "Label", "PatternPiece"))
            self.output_prefix.setText(str(Path(directory) / name))

    def _paths(self):
        from pathlib import Path
        prefix = str(self.output_prefix.text()).strip()
        if not prefix:
            raise ValueError("choose an output prefix")
        base = Path(prefix).expanduser()
        return base.with_suffix(".svg"), base.with_suffix(".dxf")

    def _refresh_validation(self):
        from freecad_cloth.pattern.PatternProductionExport import build_export_source
        try:
            source = build_export_source(
                self.obj, units=self.units.currentText(), scale=self.scale.value()
            )
            self.status.setText(
                "Ready: %d edges, %d seams, %d notches, %d marks. Native Sketcher source is authoritative."
                % (
                    len(source.pattern.segments),
                    len(source.seam_ids),
                    len(source.derived.notches),
                    len(source.derived.marks),
                )
            )
            self.status.setToolTip(
                "Authoritative Sketch: %s" % (source.sketch_name or "<unnamed>")
            )
            return True
        except Exception as exc:
            self.status.setText("Not exportable: " + str(exc))
            return False

    def _close_dialog(self):
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog() is not None:
            self.Gui.Control.closeDialog()

    def accept(self):
        from freecad_cloth.pattern.PatternProductionExport import (
            PatternExportValidationError,
            export_pattern_piece,
        )
        try:
            svg_path, dxf_path = self._paths()
            export_pattern_piece(
                self.obj,
                svg_path,
                dxf_path,
                units=self.units.currentText(),
                scale=self.scale.value(),
            )
        except PatternExportValidationError as exc:
            self.status.setText("Export blocked: " + str(exc))
            return False
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.setText("Export failed: " + str(exc))
            return False
        self.status.setText("Exported SVG and DXF: %s / %s" % (svg_path, dxf_path))
        self._close_dialog()
        return True

    def reject(self):
        self._close_dialog()
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


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
        self.width = QtWidgets.QDoubleSpinBox(); self.width.setRange(.1, 100000); self.width.setDecimals(2); self.width.setSuffix(" mm")
        self.height = QtWidgets.QDoubleSpinBox(); self.height.setRange(.1, 100000); self.height.setDecimals(2); self.height.setSuffix(" mm")
        self.width.setEnabled(not self._sketch_authoritative)
        self.height.setEnabled(not self._sketch_authoritative)
        self.allowance = QtWidgets.QDoubleSpinBox(); self.allowance.setRange(0, 1000); self.allowance.setDecimals(2); self.allowance.setSuffix(" mm")
        self.grain = QtWidgets.QDoubleSpinBox(); self.grain.setRange(-360, 360); self.grain.setDecimals(1); self.grain.setSuffix(" deg")
        for label, widget in (("Piece name", self.name), ("Geometry source", self.mode), ("Width (derived)", self.width), ("Height (derived)", self.height), ("Seam allowance", self.allowance), ("Grainline angle", self.grain)):
            layout.addRow(label, widget)
        self.edit_sketch = None
        if self._sketch_authoritative:
            self.edit_sketch = QtWidgets.QPushButton("Edit native Sketch…")
            self.edit_sketch.clicked.connect(self._edit_sketch)
            layout.addRow("Geometry editor", self.edit_sketch)
        self.mode.currentTextChanged.connect(self._mode_changed)
        if obj:
            self.name.setText(obj.Label)
            current_mode = "Sketch" if self._sketch_authoritative else str(getattr(obj, "GeometryMode", "Rectangle"))
            if self.mode.findText(current_mode) >= 0:
                self.mode.setCurrentText(current_mode)
            self.width.setValue(float(obj.Width)); self.height.setValue(float(obj.Height))
            self.allowance.setValue(float(obj.SeamAllowance)); self.grain.setValue(float(obj.GrainlineAngle))
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

    def _edit_sketch(self):
        if not self._sketch_authoritative or self.obj is None:
            return
        sketch = getattr(self.obj, "Sketch", None)
        if sketch is None:
            raise ValueError("pattern piece has no native Sketcher representation")
        active = self.Gui.activeDocument()
        if active is None:
            raise RuntimeError("no active FreeCAD document")
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
            raise ValueError("pattern piece name must not be empty")
        if not self._sketch_authoritative and self.mode.currentText() == "Rectangle" and (self.width.value() <= 0 or self.height.value() <= 0):
            raise ValueError("pattern piece dimensions must be positive")
        if self.allowance.value() < 0:
            raise ValueError("seam allowance cannot be negative")

    def _apply(self):
        self._validate()
        mode = self.mode.currentText()
        if self.obj is None:
            from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
            self.obj = create_pattern_piece_from_parameters(
                self.name.text().strip() or "PatternPiece", self.width.value(), self.height.value(),
                self.allowance.value(), self.grain.value())
        if not self._sketch_authoritative:
            if mode == "Rectangle":
                self.obj.GeometryMode = "Rectangle"
                self.obj.Width = self.width.value(); self.obj.Height = self.height.value()
            else:
                self.obj.GeometryMode = "Custom"
        else:
            # Geometry and dimensions remain owned by the linked Sketcher source.
            self.obj.GeometryMode = "Sketch"
        self.obj.SeamAllowance = self.allowance.value()
        self.obj.GrainlineAngle = self.grain.value()
        self.obj.Label = self.name.text().strip() or self.obj.Label
        self.App.ActiveDocument.recompute()
        self.Gui.activeDocument().activeView().viewTop(); self.Gui.activeDocument().activeView().fitAll()

    def _restore(self):
        if self.obj is None or self._original is None:
            return
        for key, value in self._original.items():
            setattr(self.obj, key, value)
        self.App.ActiveDocument.recompute()

    def accept(self):
        self._apply(); return True
    def reject(self):
        self._restore(); return True
    def getStandardButtons(self): return 0x00000400 | 0x00800000


class PatternDraftingTaskPanel:
    """Sketch-like 2D polygon editor with persistent semantic boundary points."""
    def __init__(self, obj):
        App, Gui, QtWidgets, QtGui, QtCore = _gui_modules()
        self.App, self.Gui, self.obj = App, Gui, obj
        from freecad_cloth.pattern.PatternDrafting import default_points, parse_points, move_point, add_point, remove_point, seam_allowance_preview
        try:
            self.points = list(parse_points(obj.DraftingBoundary))
        except (ValueError, AttributeError):
            self.points = list(default_points(obj.Width, obj.Height))
        self._original = {
            "GeometryMode": str(getattr(obj, "GeometryMode", "Custom")),
            "DraftingBoundary": str(getattr(obj, "DraftingBoundary", "")),
            "Width": float(obj.Width),
            "Height": float(obj.Height),
        }
        self.move_point, self.add_point, self.remove_point = move_point, add_point, remove_point
        self.seam_allowance_preview = seam_allowance_preview
        self.selected = 0
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — 2D Drafting")
        outer = QtWidgets.QVBoxLayout(self.form)
        self.canvas = QtWidgets.QGraphicsView()
        self.scene = QtWidgets.QGraphicsScene(self.canvas)
        self.canvas.setScene(self.scene); self.canvas.setMinimumSize(500, 360)
        outer.addWidget(self.canvas)
        self.scene.selectionChanged.connect(self._selection_changed)
        controls = QtWidgets.QHBoxLayout()
        for text, dx, dy in (("←", -5, 0), ("→", 5, 0), ("↑", 0, 5), ("↓", 0, -5)):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(lambda _=False, x=dx, y=dy: self.nudge(x, y)); controls.addWidget(button)
        add_button = QtWidgets.QPushButton("Add point")
        add_button.clicked.connect(self.add_selected_point); controls.addWidget(add_button)
        remove_button = QtWidgets.QPushButton("Remove point")
        remove_button.clicked.connect(self.remove_selected_point); controls.addWidget(remove_button)
        self.point_label = QtWidgets.QLabel("Point 0"); controls.addWidget(self.point_label)
        outer.addLayout(controls)
        outer.addWidget(QtWidgets.QLabel("Select a boundary point, then move/add/remove it. The polygon is stored as the authoritative sewing boundary."))
        self._redraw(QtGui, QtCore)

    def _selection_changed(self):
        selected = self.scene.selectedItems()
        if selected:
            index = selected[0].data(0)
            if index is not None:
                self.selected = int(index); self.point_label.setText("Point %d" % self.selected)

    def _redraw(self, QtGui, QtCore):
        self.scene.clear(); pts = self.points
        if not pts: return
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; margin = 30.
        scale = min(430. / max(1., max(xs) - min(xs)), 280. / max(1., max(ys) - min(ys)))
        def cv(p): return QtCore.QPointF((p[0] - min(xs)) * scale + margin, (max(ys) - p[1]) * scale + margin)
        poly = [cv(p) for p in pts] + [cv(pts[0])]
        self.scene.addPolygon(QtGui.QPolygonF(poly), QtGui.QPen(QtGui.QColor("#204a87"), 2))
        allowance = float(getattr(self.obj, "SeamAllowance", 0))
        if allowance:
            preview = self.seam_allowance_preview(pts, allowance)
            ap = [cv(p) for p in preview] + [cv(preview[0])]
            self.scene.addPolygon(QtGui.QPolygonF(ap), QtGui.QPen(QtGui.QColor("#888888"), 1, QtCore.Qt.DashLine))
        for i, p in enumerate(pts):
            q = cv(p)
            item = self.scene.addEllipse(q.x() - 6, q.y() - 6, 12, 12, QtGui.QPen(), QtGui.QBrush(QtGui.QColor("#c0392b")))
            item.setFlag(item.ItemIsSelectable, True); item.setData(0, i)
        for i in range(len(pts)):
            a, b = cv(pts[i]), cv(pts[(i + 1) % len(pts)]); mid = (a + b) / 2
            self.scene.addText("S%d" % i).setPos(mid.x(), mid.y())
        self.canvas.fitInView(self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20), QtCore.Qt.KeepAspectRatio)

    def _persist(self):
        from freecad_cloth.pattern.PatternDrafting import serialize_points, bounds
        self.obj.GeometryMode = "Custom"
        self.obj.DraftingBoundary = serialize_points(self.points)
        x0, y0, x1, y1 = bounds(self.points)
        self.obj.Width = max(.001, x1 - x0); self.obj.Height = max(.001, y1 - y0)
        self.App.ActiveDocument.recompute()
        _, _, _, QtGui, QtCore = _gui_modules(); self._redraw(QtGui, QtCore)

    def nudge(self, dx, dy):
        p = self.points[self.selected]
        self.points = list(self.move_point(self.points, self.selected, p[0] + dx, p[1] + dy)); self._persist()

    def add_selected_point(self):
        a = self.points[self.selected]; b = self.points[(self.selected + 1) % len(self.points)]
        point = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        self.points = list(self.add_point(self.points, point[0], point[1], self.selected + 1)); self.selected += 1; self._persist()

    def remove_selected_point(self):
        if len(self.points) <= 3:
            return
        self.points = list(self.remove_point(self.points, self.selected)); self.selected = min(self.selected, len(self.points) - 1); self._persist()

    def _restore(self):
        for key, value in self._original.items():
            setattr(self.obj, key, value)
        self.App.ActiveDocument.recompute()

    def accept(self): self._persist(); return True
    def reject(self): self._restore(); return True
    def getStandardButtons(self): return 0x00000400 | 0x00800000


def show_pattern_export_task(obj=None):
    _App, Gui, _QtWidgets, _, _ = _gui_modules()
    panel = PatternExportTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel


def show_pattern_piece_task(obj=None):
    _App, Gui, _QtWidgets, _, _ = _gui_modules(); panel = PatternPieceTaskPanel(obj); Gui.Control.showDialog(panel); return panel


def show_pattern_drafting_task(obj=None):
    App, Gui, _, _, _ = _gui_modules()
    if obj is None: obj = next((o for o in App.ActiveDocument.Objects if getattr(o, "PatternType", "") == "PatternPiece"), None)
    if obj is None: raise ValueError("create a pattern piece before opening the drafting canvas")
    panel = PatternDraftingTaskPanel(obj); Gui.Control.showDialog(panel); return panel


def show_pattern_view():
    _App, Gui, _QtWidgets, _, _ = _gui_modules()
    if Gui.activeDocument(): Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll()

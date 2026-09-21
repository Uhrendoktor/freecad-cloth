"""FreeCAD GUI for post-simulation cloth diagnostics.

The panel is read-only with respect to solver, material, simulation and target
state. It exposes one derived metric map at a time and blocks all analysis
when the simulation or DrapeTarget is stale, invalid, or non-finite.
"""


def _qt():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


def _scene(doc):
    return next((obj for obj in doc.Objects if getattr(obj, "Type", "") == "ClothSimulation"), None)


def _target_finite(target):
    source = getattr(target, "SourceObject", None)
    mesh = getattr(source, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return True
    try:
        from math import isfinite
        vertices, _triangles = topology
        return all(
            isfinite(float(getattr(point, axis)))
            for point in vertices
            for axis in ("x", "y", "z")
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _diagnostic_guard(scene):
    """Return the validated simulation/target state required by diagnostics."""
    if scene is None:
        raise RuntimeError("create a Cloth Simulation before opening diagnostics")
    if not bool(getattr(scene, "FiniteState", True)):
        raise RuntimeError("Diagnostics unavailable: simulation state is invalid/non-finite")
    simulation_state = str(getattr(scene, "SimulationState", "READY_FOR_SIMULATION")).upper()
    if simulation_state not in {"READY_FOR_SIMULATION", "READY"}:
        reason = str(getattr(scene, "InvalidationReason", "")).strip()
        detail = ": " + reason if reason else ""
        raise RuntimeError("Diagnostics unavailable: simulation state is %s%s" % (simulation_state.lower(), detail))
    if int(getattr(scene, "Steps", 0)) <= 0:
        raise RuntimeError("Diagnostics unavailable: simulation has not produced a result")
    try:
        from freecad_cloth.simulation.DrapeTarget import target_status
        status = target_status(getattr(scene, "DrapeTarget", None))
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("Diagnostics unavailable: cannot inspect DrapeTarget: %s" % exc) from exc
    if status["state"] != "ready":
        raise RuntimeError("Diagnostics unavailable: %s" % status["message"])
    proxy = getattr(scene, "Proxy", None)
    backend = getattr(proxy, "backend", None)
    finite = getattr(backend, "finite", None)
    if callable(finite) and not bool(finite()):
        raise RuntimeError("Diagnostics unavailable: simulation backend is non-finite")
    return status


def _simulation_data(scene):
    from freecad_cloth.common.ClothDiagnostics import analyze_mesh
    _diagnostic_guard(scene)
    proxy = getattr(scene, "Proxy", None)
    backend = getattr(proxy, "backend", None)
    system = getattr(backend, "system", None)
    initial = getattr(backend, "_initial", None)
    if system is None or initial is None:
        raise RuntimeError("Diagnostics unavailable: simulation result state is missing")
    current = tuple(p.position() for p in system.particles)
    rest = tuple(p.position() for p in initial.particles)
    stretch_limit = float(getattr(scene, "FabricStretch", 0.02))
    panels = []
    for panel in getattr(scene, "DrapePanels", ()):
        triangles = tuple(getattr(proxy, "panel_triangles", {}).get(panel.Name, ()))
        if not triangles:
            continue
        result = analyze_mesh(rest, current, triangles, stretch_limit=max(stretch_limit, 1e-6))
        panels.append((panel, triangles, result))
    if not panels:
        raise RuntimeError("Diagnostics unavailable: simulation has no diagnostic mesh panels")
    return panels


def _metric_range(values):
    if not values:
        return 0.0, 1.0
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-12:
        return lo, lo + 1.0
    return lo, hi


def _metric_color(value, lo, hi):
    # Blue -> green -> red ramp, normalized for a clear diagnostic overlay.
    t = max(0.0, min(1.0, (float(value) - lo) / (hi - lo)))
    if t < 0.5:
        q = t * 2.0
        return (0.0, q, 1.0 - q)
    q = (t - 0.5) * 2.0
    return (q, 1.0 - q, 0.0)


def _remove_existing_maps(scene):
    document = scene.Document
    names = [
        obj.Name
        for obj in document.Objects
        if bool(getattr(obj, "DiagnosticMap", False))
    ]
    for name in names:
        document.removeObject(name)


def create_diagnostic_map(scene, metric="stress"):
    """Create one derived Mesh::Feature colored by one validated metric."""
    App, _Gui, _QtWidgets = _qt()
    from freecad_cloth.common.ClothDiagnostics import metric_definition, summarize
    definition = metric_definition(metric)
    panels = _simulation_data(scene)

    # Validate and compute every panel before mutating the document, so a stale
    # or invalid panel can never leave behind a partial diagnostic map.
    computed = []
    for panel, triangles, result in panels:
        values = result.metric(metric)
        lo, hi = _metric_range(values)
        source_mesh = getattr(panel, "Mesh", None)
        if source_mesh is None or source_mesh.CountFacets == 0:
            raise RuntimeError("Diagnostics unavailable: panel %s has no mesh" % getattr(panel, "Name", ""))
        computed.append((panel, result, tuple(values), lo, hi, source_mesh))

    _remove_existing_maps(scene)
    created = []
    for panel, result, values, lo, hi, source_mesh in computed:
        obj = scene.Document.addObject("Mesh::Feature", "ClothDiagnostic_%s_%s" % (metric, panel.Name))
        obj.Label = "Diagnostic %s: %s" % (definition["label"], getattr(panel, "Label", panel.Name))
        obj.addProperty("App::PropertyString", "DiagnosticType", "Diagnostics").DiagnosticType = str(metric)
        obj.addProperty("App::PropertyBool", "DiagnosticMap", "Diagnostics").DiagnosticMap = True
        obj.addProperty("App::PropertyString", "Formula", "Diagnostics").Formula = definition["formula"]
        obj.addProperty("App::PropertyString", "Units", "Diagnostics").Units = definition["units"]
        obj.addProperty("App::PropertyString", "Summary", "Diagnostics").Summary = repr(summarize(result))
        obj.Mesh = source_mesh.copy()
        colors = [_metric_color(value, lo, hi) for value in values]
        if len(colors) == obj.Mesh.CountFacets:
            obj.ViewObject.DiffuseColor = colors
        obj.ViewObject.DisplayMode = "Flat Lines"
        created.append(obj)
    scene.Document.recompute()
    return created


def export_diagnostic_data(scene, metric, path):
    """Export the validated DiagnosticResult without mutating the document."""
    from freecad_cloth.common.ClothDiagnostics import export_analysis_data
    panels = _simulation_data(scene)
    values = [result for _panel, _triangles, result in panels]
    if len(values) != 1:
        # Keep the public export deterministic across panels by concatenating
        # metric values in panel order into one result-shaped payload.
        from freecad_cloth.common.ClothDiagnostics import DiagnosticResult
        result = DiagnosticResult(
            strain=tuple(v for item in values for v in item.strain),
            stress=tuple(v for item in values for v in item.stress),
            fit=tuple(v for item in values for v in item.fit),
            pressure=tuple(v for item in values for v in item.pressure),
            minimum=min(item.minimum for item in values),
            maximum=max(item.maximum for item in values),
        )
    else:
        result = values[0]
    text = export_analysis_data(result, metric)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text + "\n")
    return path


class DiagnosticsTaskPanel:
    def __init__(self, scene):
        _App, _Gui, QtWidgets = _qt()
        self.scene = scene
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothDiagnosticsTaskPanel")
        layout = QtWidgets.QVBoxLayout(self.form)

        title = QtWidgets.QLabel("Cloth Diagnostics — Read-only analysis")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        self.metric = QtWidgets.QComboBox()
        self.metric.addItems(("stress", "strain", "fit", "pressure"))
        layout.addWidget(self.metric)

        info = QtWidgets.QFormLayout()
        self.formula = QtWidgets.QLabel()
        self.formula.setWordWrap(True)
        self.units = QtWidgets.QLabel()
        self.units.setWordWrap(True)
        self.read_only = QtWidgets.QLabel("Read-only: analysis does not edit solver, material, simulation, or DrapeTarget state.")
        self.read_only.setWordWrap(True)
        info.addRow("Formula", self.formula)
        info.addRow("Units", self.units)
        layout.addLayout(info)
        layout.addWidget(self.read_only)

        self.status = QtWidgets.QLabel("Select a diagnostic map.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.refresh_button = QtWidgets.QPushButton("Refresh analysis")
        self.map_button = QtWidgets.QPushButton("Create diagnostic map")
        self.export_button = QtWidgets.QPushButton("Export diagnostic data…")
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.map_button)
        layout.addWidget(self.export_button)

        self.metric.currentTextChanged.connect(self._metric_changed)
        self.refresh_button.clicked.connect(self.refresh)
        self.map_button.clicked.connect(self.create_map)
        self.export_button.clicked.connect(self.export_data)
        layout.addStretch(1)
        self._metric_changed(self.metric.currentText())
        self.refresh()

    def _metric_changed(self, metric):
        from freecad_cloth.common.ClothDiagnostics import metric_definition
        definition = metric_definition(metric)
        self.formula.setText(definition["formula"])
        self.units.setText(definition["units"])
        self.refresh()

    def refresh(self):
        try:
            from freecad_cloth.common.ClothDiagnostics import summarize
            panels = _simulation_data(self.scene)
            summaries = [summarize(result) for _panel, _triangles, result in panels]
            metric = str(self.metric.currentText())
            values = [value for _panel, _triangles, result in panels for value in result.metric(metric)]
            lo, hi = _metric_range(values)
            self.status.setText(
                "Active metric: %s | range %.5g … %.5g | panels %d | Read-only" %
                (metric.title(), lo, hi, len(summaries))
            )
            self.map_button.setEnabled(True)
            self.export_button.setEnabled(True)
            return summaries
        except RuntimeError as exc:
            self.status.setText(str(exc) + " | Read-only")
            self.map_button.setEnabled(False)
            self.export_button.setEnabled(False)
            return []

    def create_map(self):
        try:
            created = create_diagnostic_map(self.scene, str(self.metric.currentText()))
            metric = str(self.metric.currentText())
            self.status.setText("Active metric: %s | created %d map(s) | Read-only" % (metric.title(), len(created)))
            return created
        except RuntimeError as exc:
            self.status.setText(str(exc) + " | Read-only")
            return []

    def export_data(self):
        App, _Gui, QtWidgets = _qt()
        try:
            _simulation_data(self.scene)
            path, _selected = QtWidgets.QFileDialog.getSaveFileName(
                self.form,
                "Export diagnostic data",
                "",
                "JSON files (*.json)",
            )
            if not path:
                return None
            export_diagnostic_data(self.scene, str(self.metric.currentText()), path)
            self.status.setText("Exported %s diagnostic data: %s | Read-only" % (self.metric.currentText().title(), path))
            return path
        except RuntimeError as exc:
            self.status.setText(str(exc) + " | Read-only")
            return None

    def accept(self):
        return True

    def reject(self):
        _App, Gui, _QtWidgets = _qt()
        if Gui.activeDocument() and Gui.Control.activeDialog():
            Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        _App, _Gui, QtWidgets = _qt()
        return QtWidgets.QDialogButtonBox.Close


def show_diagnostics(scene=None):
    App, Gui, _QtWidgets = _qt()
    scene = scene or _scene(App.ActiveDocument) if App.ActiveDocument else None
    if scene is None:
        raise ValueError("create a Cloth Simulation before opening diagnostics")
    panel = DiagnosticsTaskPanel(scene)
    Gui.Control.showDialog(panel)
    return panel

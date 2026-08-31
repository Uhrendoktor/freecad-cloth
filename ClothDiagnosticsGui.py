"""FreeCAD GUI for post-simulation cloth diagnostics."""


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


def _simulation_data(scene):
    from ClothDiagnostics import analyze_mesh
    proxy = getattr(scene, "Proxy", None)
    backend = getattr(proxy, "backend", None)
    system = getattr(backend, "system", None)
    initial_backend = getattr(proxy, "backend", None)
    initial = getattr(initial_backend, "_initial", None)
    if system is None or initial is None:
        raise RuntimeError("run or step the simulation before opening diagnostics")
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
        raise RuntimeError("simulation has no diagnostic mesh panels")
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


def create_diagnostic_map(scene, metric="stress"):
    """Create a derived Mesh::Feature colored by one diagnostic metric."""
    App, _Gui, _QtWidgets = _qt()
    from ClothDiagnostics import summarize
    panels = _simulation_data(scene)
    created = []
    for panel, triangles, result in panels:
        values = result.metric(metric)
        lo, hi = _metric_range(values)
        source_mesh = getattr(panel, "Mesh", None)
        if source_mesh is None or source_mesh.CountFacets == 0:
            continue
        obj = scene.Document.addObject("Mesh::Feature", "ClothDiagnostic_%s_%s" % (metric, panel.Name))
        obj.Label = "Diagnostic %s: %s" % (metric.title(), getattr(panel, "Label", panel.Name))
        obj.addProperty("App::PropertyString", "DiagnosticType", "Diagnostics").DiagnosticType = metric
        obj.addProperty("App::PropertyString", "Summary", "Diagnostics").Summary = repr(summarize(result))
        obj.Mesh = source_mesh.copy()
        colors = [_metric_color(value, lo, hi) for value in values]
        if len(colors) == obj.Mesh.CountFacets:
            obj.ViewObject.DiffuseColor = colors
        created.append(obj)
    scene.Document.recompute()
    return created


class DiagnosticsTaskPanel:
    def __init__(self, scene):
        _App, _Gui, QtWidgets = _qt()
        self.scene = scene
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.form)
        self.metric = QtWidgets.QComboBox()
        self.metric.addItems(("stress", "strain", "fit", "pressure"))
        layout.addWidget(self.metric)
        self.status = QtWidgets.QLabel("Select a diagnostic map.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh_button = QtWidgets.QPushButton("Refresh analysis")
        self.map_button = QtWidgets.QPushButton("Create diagnostic map")
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.map_button)
        self.refresh_button.clicked.connect(self.refresh)
        self.map_button.clicked.connect(self.create_map)
        layout.addStretch(1)
        self.refresh()

    def refresh(self):
        try:
            from ClothDiagnostics import summarize
            panels = _simulation_data(self.scene)
            summaries = [summarize(result) for _panel, _triangles, result in panels]
            metric = str(self.metric.currentText())
            values = [value for _panel, _triangles, result in panels for value in result.metric(metric)]
            lo, hi = _metric_range(values)
            self.status.setText(
                "%s map: %d faces | range %.5g … %.5g | panels %d" %
                (metric.title(), len(values), lo, hi, len(summaries))
            )
            return summaries
        except RuntimeError as exc:
            self.status.setText(str(exc))
            return []

    def create_map(self):
        try:
            created = create_diagnostic_map(self.scene, str(self.metric.currentText()))
            self.status.setText("Created %d %s diagnostic mesh map(s)." % (len(created), self.metric.currentText()))
            return created
        except RuntimeError as exc:
            self.status.setText(str(exc))
            return []

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

# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD GUI for post-simulation cloth diagnostics."""


def _qt() -> tuple[object, object, object]:
    """Load the FreeCAD host and supported Qt widget module.

    Returns:
        Application, GUI, and QtWidgets modules in that order.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


def _scene(doc):
    """Find the authoritative cloth simulation object in a FreeCAD document.

    Args:
        doc: Active or stored FreeCAD document to inspect.

    Returns:
        The canonical cloth simulation object, or None when no scene exists.
    """
    return next(
        (
            obj
            for obj in doc.Objects
            if getattr(obj, "Name", "") == "ClothSimulation"
            or getattr(getattr(obj, "Proxy", None), "Type", "") == "ClothSimulation"
            or getattr(obj, "Type", "") == "ClothSimulation"
        ),
        None,
    )


def _simulation_data(scene: object) -> tuple:
    """Collect validated per-panel diagnostics from the current simulation.

    Args:
        scene: Authoritative simulation object with persistent drape target data.

    Returns:
        Tuples containing a panel, its triangle indices, and computed face metrics.

    Raises:
        RuntimeError: If simulation state or the target contract prevents diagnostics.
    """
    from freecad_cloth.simulation.ClothDiagnostics import analyze_mesh

    if not bool(getattr(scene, "FiniteState", True)):
        msg = "diagnostics blocked: simulation state is non-finite"
        raise RuntimeError(msg)
    target = getattr(scene, "DrapeTarget", None)
    if target is None:
        msg = "diagnostics blocked: no persistent DrapeTarget is assigned"
        raise RuntimeError(msg)
    try:
        from freecad_cloth.simulation.DrapeTarget import target_status

        status = target_status(target)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        msg = f"diagnostics blocked: cannot inspect DrapeTarget: {exc}"
        raise RuntimeError(msg) from exc
    if status["state"] != "ready":
        raise RuntimeError("diagnostics blocked: {}".format(status["message"]))
    proxy = getattr(scene, "Proxy", None)
    backend = getattr(proxy, "backend", None)
    initial = getattr(backend, "_initial", None)
    if backend is None or initial is None:
        msg = "run or step the simulation before opening diagnostics"
        raise RuntimeError(msg)
    system = getattr(backend, "system", None)
    if system is not None:
        current = tuple(p.position() for p in system.particles)
    else:
        current = tuple(backend.positions())
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
        msg = "simulation has no diagnostic mesh panels"
        raise RuntimeError(msg)
    return panels


def _metric_range(values: tuple[float, ...]) -> tuple[float, float]:
    """Compute a display range with a non-zero span for uniform values.

    Args:
        values: Per-face metric values used to colour the diagnostic mesh.

    Returns:
        Lower and upper display bounds.
    """
    if not values:
        return 0.0, 1.0
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-12:
        return lo, lo + 1.0
    return lo, hi


def _metric_color(value: float, lo: float, hi: float) -> tuple[float, float, float]:
    """Map one normalized metric value to an RGB overlay colour.

    Args:
        value: Metric value being visualized.
        lo: Lower endpoint of the metric range.
        hi: Upper endpoint of the metric range.

    Returns:
        RGB triple interpolated across the diagnostic colour ramp.
    """
    # Blue -> green -> red ramp, normalized for a clear diagnostic overlay.
    t = max(0.0, min(1.0, (float(value) - lo) / (hi - lo)))
    if t < 0.5:
        q = t * 2.0
        return (0.0, q, 1.0 - q)
    q = (t - 0.5) * 2.0
    return (q, 1.0 - q, 0.0)


def create_diagnostic_map(scene: object, metric: str = "stress") -> tuple:
    """Create a derived Mesh::Feature coloured by one diagnostic metric.

    Args:
        scene: Simulation object whose panel meshes should be visualized.
        metric: Diagnostic metric name used to select face colours.

    Returns:
        The created diagnostic mesh objects.

    Raises:
        RuntimeError: If diagnostic inputs are invalid or no mesh facets can be mapped.
        ValueError: If the metric name is unsupported.
    """
    _App, _Gui, _QtWidgets = _qt()
    from freecad_cloth.simulation.ClothDiagnostics import metric_definition, summarize

    panels = _simulation_data(scene)
    created = []
    for panel, _triangles, result in panels:
        values = result.metric(metric)
        lo, hi = _metric_range(values)
        source_mesh = getattr(panel, "Mesh", None)
        if source_mesh is None or source_mesh.CountFacets == 0:
            continue
        obj = scene.Document.addObject("Mesh::Feature", f"ClothDiagnostic_{metric}_{panel.Name}")
        obj.Label = "Diagnostic {}: {}".format(metric.title(), getattr(panel, "Label", panel.Name))
        obj.addProperty(
            "App::PropertyString", "DiagnosticType", "Diagnostics"
        ).DiagnosticType = metric
        obj.addProperty("App::PropertyString", "Summary", "Diagnostics").Summary = repr(
            summarize(result)
        )
        definition = metric_definition(metric)
        obj.addProperty(
            "App::PropertyString", "MetricFormula", "Diagnostics"
        ).MetricFormula = definition["formula"]
        obj.addProperty(
            "App::PropertyString", "MetricUnits", "Diagnostics"
        ).MetricUnits = definition["units"]
        obj.Mesh = source_mesh.copy()
        colors = [_metric_color(value, lo, hi) for value in values]
        if len(colors) == obj.Mesh.CountFacets:
            if "FaceColors" not in getattr(obj, "PropertiesList", ()):
                obj.addProperty("App::PropertyColorList", "FaceColors", "Diagnostics")
            obj.FaceColors = colors
            if hasattr(obj.ViewObject, "Coloring"):
                obj.ViewObject.Coloring = True
        created.append(obj)
    scene.Document.recompute()
    return created


class DiagnosticsTaskPanel:
    """FreeCAD task panel for displaying and exporting cloth diagnostics."""

    def __init__(self, scene):
        """Initialize metric selection, status display, and task-panel controls.

        Args:
            scene: Authoritative cloth simulation object being inspected.
        """
        _App, _Gui, QtWidgets = _qt()
        self.scene = scene
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.form)
        self.metric = QtWidgets.QComboBox()
        self.metric.addItems(("stress", "strain", "fit", "pressure"))
        layout.addWidget(self.metric)
        self.definition = QtWidgets.QLabel()
        self.definition.setWordWrap(True)
        layout.addWidget(self.definition)
        self.status = QtWidgets.QLabel("Select a diagnostic map.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh_button = QtWidgets.QPushButton("Refresh analysis")
        self.map_button = QtWidgets.QPushButton("Create diagnostic map")
        self.export_button = QtWidgets.QPushButton("Export analysis data…")
        from freecad_cloth.common.UiDesign import mark_button

        mark_button(self.refresh_button, "secondary")
        mark_button(self.map_button, "primary")
        mark_button(self.export_button, "secondary")
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.map_button)
        layout.addWidget(self.export_button)
        self.refresh_button.clicked.connect(self.refresh)
        self.map_button.clicked.connect(self.create_map)
        self.export_button.clicked.connect(self.export_data)
        layout.addStretch(1)
        self.refresh()

        from freecad_cloth.common.UiDesign import apply_panel_style

        apply_panel_style(self.form)

    def refresh(self):
        """Refresh metric availability, aggregate values, and status messaging."""
        from freecad_cloth.common.UiDesign import set_status

        try:
            from freecad_cloth.simulation.ClothDiagnostics import metric_definition, summarize

            panels = _simulation_data(self.scene)
            summaries = [summarize(result) for _panel, _triangles, result in panels]
            metric = str(self.metric.currentText())
            values = [
                value for _panel, _triangles, result in panels for value in result.metric(metric)
            ]
            lo, hi = _metric_range(values)
            definition = metric_definition(metric)
            self.definition.setText(
                "Formula: {} | Units: {} | Read-only derived analysis".format(
                    definition["formula"], definition["units"]
                )
            )
            set_status(
                self.status,
                "%s map: %d faces | range %.5g … %.5g | panels %d"
                % (metric.title(), len(values), lo, hi, len(summaries)),
                state="success",
            )
            return summaries
        except RuntimeError as exc:
            set_status(self.status, str(exc), state="error")
            return []

    def export_data(self):
        """Export aggregated diagnostic metrics to a user-selected JSON file."""
        from freecad_cloth.common.UiDesign import set_status

        try:
            from freecad_cloth.simulation.ClothDiagnostics import export_json

            panels = _simulation_data(self.scene)
            if not panels:
                msg = "simulation has no diagnostic results"
                raise RuntimeError(msg)
            _App, _Gui, QtWidgets = _qt()
            path, _selected = QtWidgets.QFileDialog.getSaveFileName(
                self.form, "Export Cloth Analysis", "", "JSON (*.json)"
            )
            if not path:
                return []
            export_json(_merge_results(panels), path)
            set_status(
                self.status, f"Exported deterministic analysis data: {path}", state="success"
            )
            return path
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            set_status(self.status, str(exc), state="error")
            return []

    def create_map(self):
        """Create and report the current metric's derived face-colour map."""
        from freecad_cloth.common.UiDesign import set_status

        try:
            created = create_diagnostic_map(self.scene, str(self.metric.currentText()))
            set_status(
                self.status,
                "Created %d %s diagnostic mesh map(s)." % (len(created), self.metric.currentText()),
                state="success",
            )
            return created
        except RuntimeError as exc:
            set_status(self.status, str(exc), state="error")
            return []

    def accept(self):
        """Accept and close the diagnostic task panel."""
        return True

    def reject(self):
        """Close the diagnostic task panel without modifying simulation state."""
        _App, Gui, _QtWidgets = _qt()
        if Gui.activeDocument() and Gui.Control.activeDialog():
            Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        """Return the close button used by this read-only diagnostic panel.

        Returns:
            Qt button flag for closing the task panel.
        """
        _App, _Gui, QtWidgets = _qt()
        return QtWidgets.QDialogButtonBox.Close


def show_diagnostics(scene: object | None = None) -> object:
    """Open diagnostics for the supplied or active simulation scene.

    Args:
        scene: Optional simulation object; the active document scene is used by default.

    Returns:
        The diagnostic task-panel instance.

    Raises:
        ValueError: If neither an explicit scene nor an active simulation exists.
    """
    App, Gui, _QtWidgets = _qt()
    scene = scene or _scene(App.ActiveDocument) if App.ActiveDocument else None
    if scene is None:
        msg = "create a Cloth Simulation before opening diagnostics"
        raise ValueError(msg)
    panel = DiagnosticsTaskPanel(scene)
    Gui.Control.showDialog(panel)
    return panel


def _merge_results(panels: tuple) -> object:
    """Combine per-panel diagnostics into one aggregate result.

    Args:
        panels: Sequence of panel, triangle, and result triples from scene analysis.

    Returns:
        DiagnosticResult containing concatenated metric arrays and aggregate extrema.
    """
    from freecad_cloth.simulation.ClothDiagnostics import DiagnosticResult

    strain = tuple(value for _panel, _triangles, result in panels for value in result.strain)
    stress = tuple(value for _panel, _triangles, result in panels for value in result.stress)
    fit = tuple(value for _panel, _triangles, result in panels for value in result.fit)
    pressure = tuple(value for _panel, _triangles, result in panels for value in result.pressure)
    values = strain + stress + fit + pressure
    return DiagnosticResult(
        strain=strain,
        stress=stress,
        fit=fit,
        pressure=pressure,
        minimum=min(values) if values else 0.0,
        maximum=max(values) if values else 0.0,
    )

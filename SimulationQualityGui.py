"""Native FreeCAD task panel for simulation quality and fabric controls."""


def _qt():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class SimulationQualityTaskPanel:
    QUALITY_NAMES = ("Fast", "Balanced", "Final")

    def __init__(self, scene=None):
        App, Gui, QtWidgets = _qt()
        from SimulationQualityRuntimeV2 import ensure_quality_properties, apply_quality_preset
        self.App, self.Gui, self.QtWidgets = App, Gui, QtWidgets
        self.scene = scene
        self._apply_quality_preset = apply_quality_preset
        if self.scene is not None:
            ensure_quality_properties(self.scene)
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothSimulationQualityTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        quality = QtWidgets.QGroupBox("Simulation quality")
        qform = QtWidgets.QFormLayout(quality)
        self.quality = QtWidgets.QComboBox(); self.quality.addItems(self.QUALITY_NAMES)
        self.particle_distance = self._double(0.25, 100.0, 4.0, 2)
        self.iterations = self._spin(1, 200, 8)
        self.substeps = self._spin(1, 32, 1)
        qform.addRow("Preset", self.quality); qform.addRow("Particle distance (mm)", self.particle_distance)
        qform.addRow("Solver iterations", self.iterations); qform.addRow("Solver substeps", self.substeps)
        root.addWidget(quality)

        fabric = QtWidgets.QGroupBox("Fabric")
        fform = QtWidgets.QFormLayout(fabric)
        self.density = self._double(1.0, 2000.0, 150.0, 1)
        self.thickness = self._double(0.01, 10.0, 0.5, 2)
        self.stretch = self._double(0.0, 1.0, 0.02, 4)
        self.shear = self._double(0.0, 1.0, 0.02, 4)
        self.bend = self._double(0.0, 1.0, 0.01, 4)
        self.friction = self._double(0.0, 1.0, 0.5, 3)
        for label, widget in (("Density (g/m²)", self.density), ("Thickness (mm)", self.thickness),
                              ("Stretch", self.stretch), ("Shear", self.shear),
                              ("Bend", self.bend), ("Friction", self.friction)):
            fform.addRow(label, widget)
        root.addWidget(fabric)

        collision = QtWidgets.QGroupBox("Collision")
        cform = QtWidgets.QFormLayout(collision)
        self.skin_offset = self._double(0.0, 100.0, 0.0, 2)
        self.collision_radius = self._double(0.0, 10000.0, 38.0, 2)
        cform.addRow("Avatar skin offset (mm)", self.skin_offset); cform.addRow("Fallback sphere radius (mm)", self.collision_radius)
        root.addWidget(collision)

        solver = QtWidgets.QGroupBox("Run")
        sform = QtWidgets.QFormLayout(solver)
        self.steps = self._spin(0, 1000000, 0); sform.addRow("Simulation steps", self.steps); root.addWidget(solver)

        buttons = QtWidgets.QHBoxLayout()
        self.step_button = QtWidgets.QPushButton("Step"); self.run_button = QtWidgets.QPushButton("Run 30"); self.reset_button = QtWidgets.QPushButton("Reset")
        buttons.addWidget(self.step_button); buttons.addWidget(self.run_button); buttons.addWidget(self.reset_button); root.addLayout(buttons)
        self.status = QtWidgets.QLabel(); self.status.setWordWrap(True); root.addWidget(self.status); root.addStretch(1)

        self.quality.currentTextChanged.connect(self._preset_changed)
        for widget in (self.particle_distance, self.iterations, self.substeps, self.density, self.thickness,
                       self.stretch, self.shear, self.bend, self.friction, self.skin_offset, self.collision_radius):
            widget.valueChanged.connect(self._parameters_changed)
        self.step_button.clicked.connect(lambda: self.step(1)); self.run_button.clicked.connect(lambda: self.step(30)); self.reset_button.clicked.connect(self.reset)
        self._load()

    @staticmethod
    def _double(low, high, value, decimals):
        _, _, QtWidgets = _qt(); widget = QtWidgets.QDoubleSpinBox(); widget.setRange(low, high); widget.setDecimals(decimals); widget.setValue(value); return widget

    @staticmethod
    def _spin(low, high, value):
        _, _, QtWidgets = _qt(); widget = QtWidgets.QSpinBox(); widget.setRange(low, high); widget.setValue(value); return widget

    def _ensure_scene(self):
        if self.scene is None:
            from SimulationQualityRuntimeV2 import create_quality_simulation_scene
            self.scene = create_quality_simulation_scene(self.App.ActiveDocument or self.App.newDocument("ClothDrape"))
        return self.scene

    def _load(self):
        if self.scene is None:
            self.status.setText("Create or select a Cloth Simulation object."); return
        from SimulationQualityRuntimeV2 import ensure_quality_properties
        ensure_quality_properties(self.scene)
        self.quality.setCurrentText(str(self.scene.QualityPreset)); self.particle_distance.setValue(float(self.scene.ParticleDistance))
        self.iterations.setValue(int(self.scene.SolverIterations)); self.substeps.setValue(int(self.scene.SolverSubsteps))
        self.density.setValue(float(self.scene.FabricDensity)); self.thickness.setValue(float(self.scene.FabricThickness))
        self.stretch.setValue(float(self.scene.FabricStretch)); self.shear.setValue(float(self.scene.FabricShear))
        self.bend.setValue(float(self.scene.FabricBend)); self.friction.setValue(float(self.scene.FabricFriction))
        self.skin_offset.setValue(float(self.scene.AvatarSkinOffset)); self.collision_radius.setValue(float(getattr(self.scene, "CollisionRadius", 38.0)))
        self.steps.setValue(int(getattr(self.scene, "Steps", 0))); self._refresh()

    def _preset_changed(self, name):
        if self.scene is None or not name: return
        self._apply_quality_preset(self.scene, name)
        self.particle_distance.blockSignals(True); self.iterations.blockSignals(True); self.substeps.blockSignals(True)
        self.particle_distance.setValue(float(self.scene.ParticleDistance)); self.iterations.setValue(int(self.scene.SolverIterations)); self.substeps.setValue(int(self.scene.SolverSubsteps))
        self.particle_distance.blockSignals(False); self.iterations.blockSignals(False); self.substeps.blockSignals(False)
        self.scene.Document.recompute(); self._refresh()

    def _parameters_changed(self):
        if self.scene is None: return
        self.scene.ParticleDistance = self.particle_distance.value(); self.scene.SolverIterations = self.iterations.value(); self.scene.SolverSubsteps = self.substeps.value()
        self.scene.FabricDensity = self.density.value(); self.scene.FabricThickness = self.thickness.value(); self.scene.FabricStretch = self.stretch.value()
        self.scene.FabricShear = self.shear.value(); self.scene.FabricBend = self.bend.value(); self.scene.FabricFriction = self.friction.value()
        self.scene.AvatarSkinOffset = self.skin_offset.value(); self.scene.CollisionRadius = self.collision_radius.value()
        self.scene.Document.recompute(); self._refresh()

    def step(self, count):
        scene = self._ensure_scene(); self._parameters_changed(); scene.Steps = int(scene.Steps) + int(count); scene.Document.recompute()
        self.steps.setValue(int(scene.Steps)); self._refresh()
        if self.Gui.activeDocument(): self.Gui.activeDocument().activeView().fitAll()

    def reset(self):
        if self.scene is not None:
            from SimulationObjects import reset_scene
            reset_scene(self.scene)
        self.steps.setValue(0); self._refresh("Simulation reset; quality and fabric values retained.")

    def _refresh(self, message=None):
        if self.scene is None:
            self.status.setText(message or "Create or select a Cloth Simulation object."); return
        self.status.setText(message or "State: %s | %.3f s | %d particles | %d steps | %s" % (
            "ready" if bool(getattr(self.scene, "FiniteState", True)) else "invalid/non-finite", float(getattr(self.scene, "SimulatedTime", 0.0)),
            int(getattr(self.scene, "ParticleCount", 0)), int(getattr(self.scene, "Steps", 0)), str(getattr(self.scene, "QualityPreset", "Balanced"))))

    def accept(self):
        if self.scene is not None: self._parameters_changed()
        return True

    def reject(self):
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog(): self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        _, _, QtWidgets = _qt(); return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_simulation_quality_task(scene=None):
    _App, Gui, _QtWidgets = _qt(); panel = SimulationQualityTaskPanel(scene); Gui.Control.showDialog(panel); return panel

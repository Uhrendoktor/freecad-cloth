"""FreeCAD GUI controls for the Cloth Simulation workbench."""


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


class SimulationTaskPanel:
    """FreeCAD task panel for solver, material, collision and run controls."""
    MATERIALS = {
        "Cotton": (0.35, 0.20, 0.01), "Silk": (0.12, 0.08, 0.005),
        "Denim": (0.65, 0.45, 0.02), "Wool": (0.45, 0.30, 0.015),
    }

    def __init__(self, scene=None):
        App, Gui, QtCore, QtWidgets = _modules()
        self.App, self.Gui, self.QtCore, self.scene = App, Gui, QtCore, scene
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothSimulationTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        selection = QtWidgets.QGroupBox("Scene")
        layout = QtWidgets.QFormLayout(selection)
        self.cloth, self.avatar = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        self._populate_selection_lists()
        layout.addRow("Cloth pieces", self.cloth)
        layout.addRow("Collision object", self.avatar)
        root.addWidget(selection)

        material = QtWidgets.QGroupBox("Fabric")
        layout = QtWidgets.QFormLayout(material)
        self.material = QtWidgets.QComboBox(); self.material.addItems(tuple(self.MATERIALS))
        self.material.currentTextChanged.connect(self._material_changed)
        self.stretch = self._double_box(0.001, 1000.0, 0.35, 3)
        self.bend = self._double_box(0.001, 1000.0, 0.20, 3)
        self.density = self._double_box(0.0001, 100.0, 0.01, 4)
        layout.addRow("Preset", self.material)
        layout.addRow("Stretch compliance", self.stretch)
        layout.addRow("Bend compliance", self.bend)
        layout.addRow("Areal density", self.density)
        root.addWidget(material)

        solver = QtWidgets.QGroupBox("Solver")
        layout = QtWidgets.QFormLayout(solver)
        self.iterations = self._spin(1, 100, int(getattr(scene, "Iterations", 8)))
        self.timestep = self._double_box(0.0001, 1.0, float(getattr(scene, "TimeStep", 1 / 60)), 5)
        self.gravity_x = self._double_box(-50000, 50000, float(getattr(scene, "GravityX", 0)), 1)
        self.gravity_y = self._double_box(-50000, 50000, float(getattr(scene, "GravityY", 0)), 1)
        self.gravity_z = self._double_box(-50000, 50000, float(getattr(scene, "GravityZ", -9810)), 1)
        self.steps = self._spin(0, 1000000, int(getattr(scene, "Steps", 0)))
        layout.addRow("Iterations", self.iterations); layout.addRow("Time step", self.timestep)
        layout.addRow("Gravity X", self.gravity_x); layout.addRow("Gravity Y", self.gravity_y)
        layout.addRow("Gravity Z", self.gravity_z); layout.addRow("Steps", self.steps)
        root.addWidget(solver)

        collision = QtWidgets.QGroupBox("Collision")
        layout = QtWidgets.QFormLayout(collision)
        self.thickness = self._double_box(0.0, 100.0, 2.0, 2)
        self.deflection = self._double_box(0.01, 100.0, 1.0, 2)
        self.collision_radius = self._double_box(0.0, 10000.0, float(getattr(scene, "CollisionRadius", 38.0)), 2)
        layout.addRow("Thickness", self.thickness); layout.addRow("Mesh deflection", self.deflection)
        layout.addRow("Sphere radius", self.collision_radius)
        root.addWidget(collision)

        sewing = QtWidgets.QGroupBox("Sewing & pinning")
        layout = QtWidgets.QFormLayout(sewing)
        self.pins = QtWidgets.QLineEdit(self._join(getattr(scene, "PinSelection", [])))
        self.seams = QtWidgets.QLineEdit(self._join(getattr(scene, "SeamSelection", [])))
        self.pins.setToolTip("Particle indices separated by commas")
        self.seams.setToolTip("Particle pairs such as 3-27 separated by semicolons")
        layout.addRow("Pinned vertices", self.pins); layout.addRow("Seam pairs", self.seams)
        root.addWidget(sewing)

        controls = QtWidgets.QHBoxLayout()
        self.step_button = QtWidgets.QPushButton("Step")
        self.run_button = QtWidgets.QPushButton("Run 30 steps")
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.step_button.setObjectName("ClothSimulationStepButton")
        self.run_button.setObjectName("ClothSimulationRunButton")
        self.reset_button.setObjectName("ClothSimulationResetButton")
        self.step_button.setToolTip("Advance the simulation by one step")
        self.run_button.setToolTip("Run the simulation for 30 steps")
        self.reset_button.setToolTip("Reset simulation state while retaining selections")
        self.run_button.setDefault(True)
        self.run_button.setAutoDefault(True)
        controls.addWidget(self.step_button); controls.addWidget(self.run_button); controls.addWidget(self.reset_button)
        root.addLayout(controls)

        self.status = QtWidgets.QLabel(); self.status.setWordWrap(True); root.addWidget(self.status); root.addStretch(1)
        self.step_button.clicked.connect(lambda: self.step(1))
        self.run_button.clicked.connect(lambda: self.step(30))
        self.reset_button.clicked.connect(self.reset)
        self.cloth.currentIndexChanged.connect(self._selection_changed)
        self.avatar.currentIndexChanged.connect(self._selection_changed)
        self.pins.editingFinished.connect(self._selection_changed); self.seams.editingFinished.connect(self._selection_changed)
        for widget in (self.iterations, self.timestep, self.gravity_x, self.gravity_y, self.gravity_z, self.collision_radius):
            widget.valueChanged.connect(self._parameters_changed)
        self.thickness.valueChanged.connect(self._collision_changed); self.deflection.valueChanged.connect(self._collision_changed)
        self.status.setText("Select a simulation scene or create one with Create Simulation.")
        self._load_scene_values()

    @staticmethod
    def _join(values): return ",".join(str(v) for v in values or [])

    @staticmethod
    def _double_box(low, high, value, decimals):
        _, _, _, QtWidgets = _modules(); box = QtWidgets.QDoubleSpinBox()
        box.setRange(low, high); box.setDecimals(decimals); box.setValue(value); return box

    @staticmethod
    def _spin(low, high, value):
        _, _, _, QtWidgets = _modules(); box = QtWidgets.QSpinBox()
        box.setRange(low, high); box.setValue(value); return box

    def _ensure_property(self, name, type_name, group, default):
        if self.scene is None or hasattr(self.scene, name): return
        self.scene.addProperty(type_name, name, group); setattr(self.scene, name, default)

    def _load_scene_values(self):
        if self.scene is None: return
        for name, type_name, default in (("MaterialPreset", "App::PropertyString", "Cotton"), ("StretchCompliance", "App::PropertyFloat", 0.35), ("BendCompliance", "App::PropertyFloat", 0.20), ("ArealDensity", "App::PropertyFloat", 0.01)):
            self._ensure_property(name, type_name, "Fabric", default)
        index = self.material.findText(str(getattr(self.scene, "MaterialPreset", "Cotton")))
        self.material.setCurrentIndex(index if index >= 0 else 0)
        self.stretch.setValue(float(getattr(self.scene, "StretchCompliance", 0.35)))
        self.bend.setValue(float(getattr(self.scene, "BendCompliance", 0.20)))
        self.density.setValue(float(getattr(self.scene, "ArealDensity", 0.01)))
        self._refresh_status()

    def _populate_selection_lists(self):
        self.cloth.clear(); self.avatar.clear(); doc = self.App.ActiveDocument
        if doc is None: return
        for obj in doc.Objects:
            if getattr(obj, "ClothMeshType", "") or getattr(obj, "PatternType", "") == "PatternPiece": self.cloth.addItem(obj.Label, obj.Name)
            if getattr(obj, "CollisionType", ""): self.avatar.addItem(obj.Label, obj.Name)
        if self.scene is not None:
            for obj in getattr(self.scene, "ClothPieces", ()):
                index = self.cloth.findData(obj.Name)
                if index >= 0: self.cloth.setCurrentIndex(index)
            avatar = getattr(self.scene, "AvatarProxy", None)
            if avatar is not None:
                index = self.avatar.findData(avatar.Name)
                if index >= 0: self.avatar.setCurrentIndex(index)

    def _selection_changed(self):
        if self.scene is None: return
        if self.cloth.currentData():
            obj = self.scene.Document.getObject(self.cloth.currentData())
            if obj: self.scene.ClothPieces = [obj]
        if self.avatar.currentData():
            obj = self.scene.Document.getObject(self.avatar.currentData())
            if obj: self.scene.AvatarProxy = obj
        self.scene.PinSelection = [p.strip() for p in self.pins.text().replace(";", ",").split(",") if p.strip()]
        self.scene.SeamSelection = [p.strip() for p in self.seams.text().replace(",", ";").split(";") if p.strip()]
        self.scene.Document.recompute(); self._refresh_status()

    def _material_changed(self, preset):
        if self.scene is None: return
        values = self.MATERIALS.get(str(preset), self.MATERIALS["Cotton"])
        self.stretch.setValue(values[0]); self.bend.setValue(values[1]); self.density.setValue(values[2])
        for name, type_name, default in (("MaterialPreset", "App::PropertyString", "Cotton"), ("StretchCompliance", "App::PropertyFloat", 0.35), ("BendCompliance", "App::PropertyFloat", 0.20), ("ArealDensity", "App::PropertyFloat", 0.01)):
            self._ensure_property(name, type_name, "Fabric", default)
        self.scene.MaterialPreset = str(preset); self.scene.StretchCompliance = values[0]; self.scene.BendCompliance = values[1]; self.scene.ArealDensity = values[2]
        self.scene.Document.recompute()

    def _parameters_changed(self):
        if self.scene is None: return
        self.scene.Iterations = self.iterations.value(); self.scene.TimeStep = self.timestep.value()
        self.scene.GravityX = self.gravity_x.value(); self.scene.GravityY = self.gravity_y.value(); self.scene.GravityZ = self.gravity_z.value()
        self.scene.CollisionRadius = self.collision_radius.value(); self.scene.Document.recompute(); self._refresh_status()

    def _collision_changed(self):
        if self.scene is None: return
        avatar = getattr(self.scene, "AvatarProxy", None)
        if avatar is not None: avatar.CollisionThickness = self.thickness.value(); avatar.CollisionDeflection = self.deflection.value()
        self.scene.Document.recompute(); self._refresh_status()

    def _ensure_scene(self):
        if self.scene is None:
            from SimulationObjects import create_simulation_scene
            self.scene = create_simulation_scene(self.App.ActiveDocument or self.App.newDocument("ClothDrape"))
            self._populate_selection_lists(); self._load_scene_values()
        self._parameters_changed(); self._selection_changed(); return self.scene

    def step(self, count):
        scene = self._ensure_scene(); scene.Steps = int(scene.Steps) + int(count); scene.Document.recompute(); self.steps.setValue(int(scene.Steps)); self._refresh_status()
        if self.Gui.activeDocument(): self.Gui.activeDocument().activeView().fitAll()

    def reset(self):
        if self.scene is not None:
            from SimulationObjects import reset_scene
            reset_scene(self.scene)
        self.steps.setValue(0); self._refresh_status("Simulation reset; selections retained.")

    def _refresh_status(self, message=None):
        if self.scene is None: self.status.setText(message or "Select a simulation scene or create one with Create Simulation."); return
        state = "ready" if bool(getattr(self.scene, "FiniteState", True)) else "invalid/non-finite"
        self.status.setText(message or "State: %s | %.3f s | %d particles | %d steps" % (state, float(getattr(self.scene, "SimulatedTime", 0.0)), int(getattr(self.scene, "ParticleCount", 0)), int(getattr(self.scene, "Steps", 0))))

    def accept(self): self._ensure_scene().Document.recompute(); return True

    def reject(self):
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog(): self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        _, _, _, QtWidgets = _modules(); return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_simulation_task(scene=None):
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = SimulationTaskPanel(scene); Gui.Control.showDialog(panel); return panel

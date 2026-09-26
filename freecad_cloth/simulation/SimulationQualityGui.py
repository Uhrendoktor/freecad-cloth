"""Native FreeCAD task panel for simulation quality and fabric controls."""


_TARGET_BLOCKED_STATES = frozenset({"stale", "unbuilt", "unassigned", "invalid", "missing", "disabled"})


def target_is_blocked(target_info):
    """Return whether a target lifecycle summary must block Step/Run."""
    return str((target_info or {}).get("state", "missing")) in _TARGET_BLOCKED_STATES

def _qt():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets, QtGui
    except ImportError:
        from PySide2 import QtWidgets, QtGui
    return App, Gui, QtWidgets, QtGui

class SimulationQualityTaskPanel:
    QUALITY_NAMES = ("Fast", "Balanced", "Final")
    SNAPSHOT_PROPERTIES = (
        "QualityPreset", "ParticleDistance", "SolverIterations", "SolverSubsteps",
        "FabricDensity", "FabricThickness", "FabricStretch", "FabricShear",
        "FabricBend", "FabricFriction", "FabricColor", "FabricSpecular",
        "FabricRoughness", "FabricTransparency", "AvatarSkinOffset", "CollisionRadius", "Steps",
    )

    def __init__(self, scene=None):
        App, Gui, QtWidgets, QtGui = _qt()
        from freecad_cloth.simulation.SimulationQualityRuntimeV2 import ensure_quality_properties, apply_quality_preset
        self.App, self.Gui, self.QtWidgets, self.QtGui = App, Gui, QtWidgets, QtGui
        self.scene = scene
        self._apply_quality_preset = apply_quality_preset
        self._snapshot = None
        if self.scene is not None:
            ensure_quality_properties(self.scene)
        self.form = QtWidgets.QWidget(); self.form.setObjectName("ClothSimulationQualityTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)
        context = QtWidgets.QGroupBox("Context"); cform = QtWidgets.QFormLayout(context)
        self.target_context = QtWidgets.QLabel(); self.target_context.setWordWrap(True)
        self.refresh_target_button = QtWidgets.QPushButton("Refresh target")
        self.refresh_target_button.setObjectName("ClothSimulationRefreshTargetButton")
        self.refresh_target_button.setToolTip("Recover the current DrapeTarget using its existing validation and refresh paths.")
        cform.addRow("Target", self.target_context)
        cform.addRow("", self.refresh_target_button)
        root.addWidget(context)

        fitting = QtWidgets.QGroupBox("Arrange / Fit")
        flayout = QtWidgets.QVBoxLayout(fitting)
        self.fitting_status = QtWidgets.QLabel("No simulation scene selected.")
        self.fitting_status.setWordWrap(True)
        self.fitting_status.setObjectName("ClothSimulationFittingStatus")
        self.arrange_fit_button = QtWidgets.QPushButton("Arrange / Fit…")
        self.arrange_fit_button.setObjectName("ClothSimulationArrangeFitButton")
        self.arrange_fit_button.setToolTip("Open the existing fitting stage with the current simulation garment pieces.")
        self.reset_arrangement_button = QtWidgets.QPushButton("Reset arrangement")
        self.reset_arrangement_button.setObjectName("ClothSimulationResetArrangementButton")
        self.reset_arrangement_button.setToolTip("Restore the fitting stage to its saved pre-arrangement placements.")
        self.reset_arrangement_button.setEnabled(False)
        flayout.addWidget(self.fitting_status)
        fit_buttons = QtWidgets.QHBoxLayout()
        fit_buttons.addWidget(self.arrange_fit_button)
        fit_buttons.addWidget(self.reset_arrangement_button)
        flayout.addLayout(fit_buttons)
        root.addWidget(fitting)

        quality = QtWidgets.QGroupBox("Simulation quality"); qform = QtWidgets.QFormLayout(quality)
        self.quality = QtWidgets.QComboBox(); self.quality.addItems(self.QUALITY_NAMES)
        self.particle_distance = self._double(0.25, 100.0, 4.0, 2)
        self.iterations = self._spin(1, 200, 8); self.substeps = self._spin(1, 32, 1)
        qform.addRow("Preset", self.quality); qform.addRow("Particle distance (mm)", self.particle_distance); qform.addRow("Solver iterations", self.iterations); qform.addRow("Solver substeps", self.substeps); root.addWidget(quality)
        fabric = QtWidgets.QGroupBox("Fabric"); fform = QtWidgets.QFormLayout(fabric)
        self.density = self._double(1.0, 2000.0, 150.0, 1); self.thickness = self._double(0.01, 10.0, 0.5, 2); self.stretch = self._double(0.0, 1.0, 0.02, 4); self.shear = self._double(0.0, 1.0, 0.02, 4); self.bend = self._double(0.0, 1.0, 0.01, 4); self.friction = self._double(0.0, 1.0, 0.5, 3)
        self.fabric_color = QtWidgets.QPushButton("Choose fabric color")
        self.specular = self._double(0.0, 1.0, 0.25, 3)
        self.roughness = self._double(0.0, 1.0, 0.65, 3)
        self.transparency = self._spin(0, 100, 0)
        for label, widget in (("Density (g/m²)", self.density), ("Thickness (mm)", self.thickness), ("Stretch", self.stretch), ("Shear", self.shear), ("Bend", self.bend), ("Friction", self.friction), ("Color", self.fabric_color), ("Specular", self.specular), ("Roughness", self.roughness), ("Transparency (%)", self.transparency)): fform.addRow(label, widget)
        root.addWidget(fabric)
        collision = QtWidgets.QGroupBox("Collision"); cform = QtWidgets.QFormLayout(collision)
        self.skin_offset = self._double(0.0, 100.0, 0.0, 2); self.collision_radius = self._double(0.0, 10000.0, 38.0, 2)
        cform.addRow("Avatar skin offset (mm)", self.skin_offset); cform.addRow("Fallback sphere radius (mm)", self.collision_radius); root.addWidget(collision)
        solver = QtWidgets.QGroupBox("Run"); sform = QtWidgets.QFormLayout(solver)
        self.steps = self._spin(0, 1000000, 0); sform.addRow("Simulation steps", self.steps); root.addWidget(solver)
        buttons = QtWidgets.QHBoxLayout(); self.step_button = QtWidgets.QPushButton("Step"); self.run_button = QtWidgets.QPushButton("Run 30"); self.reset_button = QtWidgets.QPushButton("Reset")
        buttons.addWidget(self.step_button); buttons.addWidget(self.run_button); buttons.addWidget(self.reset_button); root.addLayout(buttons)
        self.status = QtWidgets.QLabel(); self.status.setWordWrap(True); root.addWidget(self.status); root.addStretch(1)
        self.arrange_fit_button.clicked.connect(self.open_arrange_fit)
        self.reset_arrangement_button.clicked.connect(self.reset_arrangement)
        self.refresh_target_button.clicked.connect(self._refresh_target)
        self.quality.currentTextChanged.connect(self._preset_changed)
        self.fabric_color.clicked.connect(self._choose_fabric_color)
        for widget in (self.particle_distance, self.iterations, self.substeps, self.density, self.thickness, self.stretch, self.shear, self.bend, self.friction, self.specular, self.roughness, self.transparency, self.skin_offset, self.collision_radius): widget.valueChanged.connect(self._parameters_changed)
        self.step_button.clicked.connect(lambda: self.step(1)); self.run_button.clicked.connect(lambda: self.step(30)); self.reset_button.clicked.connect(self.reset)
        self._load()

    @staticmethod
    def _double(low, high, value, decimals):
        _, _, QtWidgets, _ = _qt(); widget = QtWidgets.QDoubleSpinBox(); widget.setRange(low, high); widget.setDecimals(decimals); widget.setValue(value); return widget

    @staticmethod
    def _spin(low, high, value):
        _, _, QtWidgets, _ = _qt(); widget = QtWidgets.QSpinBox(); widget.setRange(low, high); widget.setValue(value); return widget

    def _refresh_fitting_stage(self):
        from freecad_cloth.simulation.FittingHandoff import fitting_stage_status
        message, can_reset = fitting_stage_status(self.scene)
        self.fitting_status.setText(message)
        self.reset_arrangement_button.setEnabled(bool(can_reset))

    def open_arrange_fit(self):
        if self.scene is None:
            self.status.setText("Create or select a Cloth Simulation object before opening Arrange / Fit.")
            return
        try:
            from freecad_cloth.simulation.FittingHandoff import open_arrange_fit_from_simulation
            open_arrange_fit_from_simulation(self.scene)
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.status.setText("Arrange / Fit unavailable — %s" % exc)

    def reset_arrangement(self):
        try:
            from freecad_cloth.simulation.FittingHandoff import reset_arrangement_from_simulation
            reset_arrangement_from_simulation()
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.status.setText("Arrangement reset unavailable — %s" % exc)
            return
        self._refresh()

    def _refresh_target(self):
        if self.scene is None:
            return
        target = getattr(self.scene, "DrapeTarget", None)
        try:
            from freecad_cloth.simulation.DrapeTarget import refresh_drape_target, target_status
            info = target_status(target)
            if info["state"] == "disabled":
                from freecad_cloth.simulation.DrapeCommands import set_drape_target_enabled
                set_drape_target_enabled(True)
                self._refresh("Drape target enabled.")
                return
            if info["state"] in {"invalid", "unassigned"}:
                if target is None:
                    raise ValueError(info["message"])
                from freecad_cloth.simulation.DrapeCommands import edit_drape_target
                edit_drape_target()
                self._refresh("Drape target editor opened.")
                return
            if getattr(target, "SourceObject", None) is None:
                raise ValueError(info["message"])
            refresh_drape_target(target)
            self.scene.Document.recompute()
            self._refresh("Drape target refreshed.")
        except Exception as exc:
            self._refresh("Drape target recovery blocked — %s" % exc)

    def _ensure_scene(self):
        if self.scene is None:
            from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
            self.scene = create_quality_simulation_scene(self.App.ActiveDocument or self.App.newDocument("ClothDrape"))
        return self.scene

    def _capture_snapshot(self):
        if self.scene is None:
            self._snapshot = None
            return
        self._snapshot = {name: getattr(self.scene, name) for name in self.SNAPSHOT_PROPERTIES if hasattr(self.scene, name)}

    def _restore_snapshot(self):
        if self.scene is None or self._snapshot is None:
            return
        for name, value in self._snapshot.items():
            setattr(self.scene, name, value)
        self.scene.Document.recompute()
        self._load_widgets_only()
        self._refresh()

    def _set_color_button(self, color):
        r = int(max(0, min(255, round(float(color[0]) * 255))))
        g = int(max(0, min(255, round(float(color[1]) * 255))))
        b = int(max(0, min(255, round(float(color[2]) * 255))))
        self._fabric_qcolor = self.QtGui.QColor(r, g, b)
        self.fabric_color.setStyleSheet("background-color: rgb(%d,%d,%d)" % (r, g, b))

    def _choose_fabric_color(self):
        current = getattr(self, "_fabric_qcolor", self.QtGui.QColor(184, 87, 117))
        chosen = self.QtGui.QColorDialog.getColor(current, self.form, "Fabric color")
        if not chosen.isValid():
            return
        self._fabric_qcolor = chosen
        self._set_color_button((chosen.red() / 255.0, chosen.green() / 255.0, chosen.blue() / 255.0))
        self._parameters_changed()

    def _load_widgets_only(self):
        if self.scene is None:
            return
        widgets = [self.quality, self.particle_distance, self.iterations, self.substeps, self.density, self.thickness, self.stretch, self.shear, self.bend, self.friction, self.specular, self.roughness, self.transparency, self.skin_offset, self.collision_radius, self.steps]
        for widget in widgets: widget.blockSignals(True)
        try:
            self.quality.setCurrentText(str(self.scene.QualityPreset)); self.particle_distance.setValue(float(self.scene.ParticleDistance)); self.iterations.setValue(int(self.scene.SolverIterations)); self.substeps.setValue(int(self.scene.SolverSubsteps))
            self.density.setValue(float(self.scene.FabricDensity)); self.thickness.setValue(float(self.scene.FabricThickness)); self.stretch.setValue(float(self.scene.FabricStretch)); self.shear.setValue(float(self.scene.FabricShear)); self.bend.setValue(float(self.scene.FabricBend)); self.friction.setValue(float(self.scene.FabricFriction))
            self.specular.setValue(float(self.scene.FabricSpecular)); self.roughness.setValue(float(self.scene.FabricRoughness)); self.transparency.setValue(int(self.scene.FabricTransparency))
            self._set_color_button(tuple(float(value) for value in self.scene.FabricColor))
            self.skin_offset.setValue(float(self.scene.AvatarSkinOffset)); self.collision_radius.setValue(float(getattr(self.scene, "CollisionRadius", 38.0))); self.steps.setValue(int(getattr(self.scene, "Steps", 0)))
        finally:
            for widget in widgets: widget.blockSignals(False)

    def _load(self):
        if self.scene is None:
            self._refresh("Create or select a Cloth Simulation object.")
            return
        from freecad_cloth.simulation.SimulationQualityRuntimeV2 import ensure_quality_properties
        ensure_quality_properties(self.scene)
        self._load_widgets_only()
        self._capture_snapshot()
        self._refresh()

    def _preset_changed(self, name):
        if self.scene is None or not name: return
        self._apply_quality_preset(self.scene, name)
        self.particle_distance.blockSignals(True); self.iterations.blockSignals(True); self.substeps.blockSignals(True)
        self.particle_distance.setValue(float(self.scene.ParticleDistance)); self.iterations.setValue(int(self.scene.SolverIterations)); self.substeps.setValue(int(self.scene.SolverSubsteps))
        self.particle_distance.blockSignals(False); self.iterations.blockSignals(False); self.substeps.blockSignals(False)
        self.scene.Document.recompute(); self._refresh("Preset applied. Cancel restores the values from when this panel opened.")

    def _parameters_changed(self):
        if self.scene is None: return
        color = getattr(self, "_fabric_qcolor", None)
        self.scene.ParticleDistance = self.particle_distance.value(); self.scene.SolverIterations = self.iterations.value(); self.scene.SolverSubsteps = self.substeps.value(); self.scene.FabricDensity = self.density.value(); self.scene.FabricThickness = self.thickness.value(); self.scene.FabricStretch = self.stretch.value(); self.scene.FabricShear = self.shear.value(); self.scene.FabricBend = self.bend.value(); self.scene.FabricFriction = self.friction.value(); self.scene.FabricSpecular = self.specular.value(); self.scene.FabricRoughness = self.roughness.value(); self.scene.FabricTransparency = self.transparency.value()
        if color is not None:
            self.scene.FabricColor = (color.redF(), color.greenF(), color.blueF())
        self.scene.AvatarSkinOffset = self.skin_offset.value(); self.scene.CollisionRadius = self.collision_radius.value(); self.scene.Document.recompute(); self._refresh("Changes are applied live. Cancel restores the panel-open state.")

    def step(self, count):
        scene = self._ensure_scene()
        from freecad_cloth.simulation.DrapeTarget import target_status
        status = target_status(getattr(scene, "DrapeTarget", None))
        if target_is_blocked(status):
            self._refresh()
            raise RuntimeError(status["message"])
        self._parameters_changed(); scene.Steps = int(scene.Steps) + int(count); scene.Document.recompute(); self.steps.setValue(int(scene.Steps)); self._refresh()
        if self.Gui.activeDocument(): self.Gui.activeDocument().activeView().fitAll()

    def reset(self):
        if self.scene is not None:
            from freecad_cloth.simulation.SimulationObjects import reset_scene
            reset_scene(self.scene)
        self.steps.setValue(0); self._refresh("Simulation reset; quality and fabric values retained.")

    def _refresh(self, message=None):
        self._refresh_fitting_stage()
        if self.scene is None:
            self.step_button.setEnabled(False); self.run_button.setEnabled(False); self.reset_button.setEnabled(False)
            self.arrange_fit_button.setEnabled(False)
            self.refresh_target_button.setEnabled(False)
            self.target_context.setText("No simulation scene is selected.")
            self.status.setText(message or "Create or select a Cloth Simulation object.")
            return
        from freecad_cloth.simulation.DrapeTarget import target_status
        target_info = target_status(getattr(self.scene, "DrapeTarget", None))
        blocked = target_is_blocked(target_info)
        self.step_button.setEnabled(not blocked)
        self.run_button.setEnabled(not blocked)
        self.reset_button.setEnabled(True)
        self.arrange_fit_button.setEnabled(True)
        self.target_context.setText(str(target_info["message"]))
        target = getattr(self.scene, "DrapeTarget", None)
        target_source = getattr(target, "SourceObject", None)
        if target_info["state"] == "disabled":
            self.refresh_target_button.setText("Enable target")
            self.refresh_target_button.setEnabled(target is not None)
        elif target_info["state"] in {"invalid", "unassigned"}:
            self.refresh_target_button.setText("Edit target")
            self.refresh_target_button.setEnabled(target is not None)
        else:
            self.refresh_target_button.setText("Refresh target")
            self.refresh_target_button.setEnabled(bool(target_source) and target_info["state"] != "ready")

        if blocked:
            text = "Simulation blocked — %s" % target_info["message"]
        elif message:
            text = message
        else:
            text = "State: %s | %.3f s | %d particles | %d steps | %s | target: %s" % (
                "ready" if bool(getattr(self.scene, "FiniteState", True)) else "invalid/non-finite",
                float(getattr(self.scene, "SimulatedTime", 0.0)),
                int(getattr(self.scene, "ParticleCount", 0)),
                int(getattr(self.scene, "Steps", 0)),
                str(getattr(self.scene, "QualityPreset", "Balanced")),
                target_info["state"],
            )
        self.status.setText(text)
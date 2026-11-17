# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD GUI controls for the Cloth Simulation workbench."""

from typing import TYPE_CHECKING, ClassVar

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    if TYPE_CHECKING:
        from PySide2 import QtCore, QtWidgets
    else:
        try:
            from PySide import QtCore, QtWidgets
        except ImportError:
            from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


class SimulationTaskPanel:
    """Task panel for fabric, target, solver and simulation actions.

    Collision selection is deliberately target-neutral: the persistent
    ``DrapeTarget`` object is authoritative and can reference either the Cloth
    mannequin or arbitrary FreeCAD Shape/Mesh geometry.
    """

    MATERIALS: ClassVar[dict[str, tuple[float, float, float]]] = {
        "Cotton": (0.35, 0.20, 0.01),
        "Silk": (0.12, 0.08, 0.005),
        "Denim": (0.65, 0.45, 0.02),
        "Wool": (0.45, 0.30, 0.015),
    }

    def __init__(self, scene=None):
        App, Gui, QtCore, QtWidgets = _modules()
        self.App, self.Gui, self.QtCore, self.scene = App, Gui, QtCore, scene
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothSimulationTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)

        from freecad_cloth.common.UiDesign import configure_form_layout

        selection = QtWidgets.QGroupBox("Scene")
        layout = QtWidgets.QFormLayout(selection)
        configure_form_layout(layout, QtWidgets)
        self.cloth, self.target = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        self._populate_selection_lists()
        self.cloth_view_button = QtWidgets.QPushButton("Select")
        self.cloth_view_button.setToolTip(
            "Highlight the selected cloth object in the FreeCAD viewport without moving the camera."
        )
        self.target_view_button = QtWidgets.QPushButton("Select")
        self.target_view_button.setToolTip(
            "Highlight the Drape Target's linked collision source in the viewport "
            "without moving the camera."
        )
        for combo, button in (
            (self.cloth, self.cloth_view_button),
            (self.target, self.target_view_button),
        ):
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(combo, 1)
            row_layout.addWidget(button)
            layout.addRow(
                "Cloth pieces" if combo is self.cloth else "Drape target",
                row,
            )
        content_layout.addWidget(selection)

        material = QtWidgets.QGroupBox("Fabric")
        layout = QtWidgets.QFormLayout(material)
        configure_form_layout(layout, QtWidgets)
        self.material = QtWidgets.QComboBox()
        self.material.addItems(tuple(self.MATERIALS))
        self.material.currentTextChanged.connect(self._material_changed)
        self.stretch = self._double_box(0.001, 1000.0, 0.35, 3)
        self.bend = self._double_box(0.001, 1000.0, 0.20, 3)
        self.density = self._double_box(0.0001, 100.0, 0.01, 4)
        layout.addRow("Preset", self.material)
        layout.addRow("Stretch compliance", self.stretch)
        layout.addRow("Bend compliance", self.bend)
        layout.addRow("Areal density", self.density)
        content_layout.addWidget(material)

        advanced_content = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(advanced_content)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(6)

        solver = QtWidgets.QGroupBox("Solver")
        layout = QtWidgets.QFormLayout(solver)
        configure_form_layout(layout, QtWidgets)
        self.iterations = self._spin(1, 100, int(getattr(scene, "Iterations", 8)))
        self.timestep = self._double_box(0.0001, 1.0, float(getattr(scene, "TimeStep", 1 / 60)), 5)
        self.gravity_x = self._double_box(-50000, 50000, float(getattr(scene, "GravityX", 0)), 1)
        self.gravity_y = self._double_box(-50000, 50000, float(getattr(scene, "GravityY", 0)), 1)
        self.gravity_z = self._double_box(
            -50000, 50000, float(getattr(scene, "GravityZ", -9810)), 1
        )
        self.steps = self._spin(0, 1000000, int(getattr(scene, "Steps", 0)))
        layout.addRow("Iterations", self.iterations)
        layout.addRow("Time step", self.timestep)
        layout.addRow("Gravity X", self.gravity_x)
        layout.addRow("Gravity Y", self.gravity_y)
        layout.addRow("Gravity Z", self.gravity_z)
        layout.addRow("Steps", self.steps)
        advanced_layout.addWidget(solver)

        collision = QtWidgets.QGroupBox("Drape target collision")
        layout = QtWidgets.QFormLayout(collision)
        configure_form_layout(layout, QtWidgets)
        self.thickness = self._double_box(0.0, 100.0, 2.0, 2)
        self.deflection = self._double_box(0.01, 100.0, 1.0, 2)
        self.collision_radius = self._double_box(
            0.0, 10000.0, float(getattr(scene, "CollisionRadius", 38.0)), 2
        )
        layout.addRow("Thickness", self.thickness)
        layout.addRow("Mesh deflection", self.deflection)
        layout.addRow("Legacy sphere radius", self.collision_radius)
        advanced_layout.addWidget(collision)

        sewing = QtWidgets.QGroupBox("Sewing & pinning")
        layout = QtWidgets.QFormLayout(sewing)
        configure_form_layout(layout, QtWidgets)
        self.pins = QtWidgets.QLineEdit(self._join(getattr(scene, "PinSelection", [])))
        self.seams = QtWidgets.QLineEdit(self._join(getattr(scene, "SeamSelection", [])))
        self.pins.setToolTip("Particle indices separated by commas")
        self.seams.setToolTip("Particle pairs such as 3-27 separated by semicolons")
        layout.addRow("Pinned vertices", self.pins)
        layout.addRow("Seam pairs", self.seams)
        advanced_layout.addWidget(sewing)
        from freecad_cloth.common.UiDesign import make_disclosure

        self.advanced_section, self.advanced_toggle = make_disclosure(
            "Advanced solver, collision & sewing settings", advanced_content, QtCore, QtWidgets
        )
        content_layout.addWidget(self.advanced_section)

        from freecad_cloth.common.UiDesign import make_scroll_area

        root.addWidget(make_scroll_area(content, QtWidgets), 1)

        controls = QtWidgets.QHBoxLayout()
        self.step_button = QtWidgets.QPushButton("Step")
        self.run_button = QtWidgets.QPushButton("Run 30 steps")
        self.reset_button = QtWidgets.QPushButton("Reset")
        from freecad_cloth.common.UiDesign import mark_button

        mark_button(self.cloth_view_button, "secondary")
        mark_button(self.target_view_button, "secondary")
        mark_button(self.step_button, "secondary")
        mark_button(self.run_button, "primary")
        mark_button(self.reset_button, "danger")
        self.step_button.setObjectName("ClothSimulationStepButton")
        self.run_button.setObjectName("ClothSimulationRunButton")
        self.reset_button.setObjectName("ClothSimulationResetButton")
        self.step_button.setToolTip("Advance the simulation by one step")
        self.run_button.setToolTip("Run the simulation for 30 steps")
        self.reset_button.setToolTip("Reset simulation state while retaining selections")
        self.run_button.setDefault(True)
        self.run_button.setAutoDefault(True)
        controls.addWidget(self.step_button)
        controls.addWidget(self.run_button)
        controls.addWidget(self.reset_button)
        root.addLayout(controls)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)
        self.step_button.clicked.connect(lambda: self.step(1))
        self.run_button.clicked.connect(lambda: self.step(30))
        self.reset_button.clicked.connect(self.reset)
        self.cloth_view_button.clicked.connect(self._select_cloth_in_viewport)
        self.target_view_button.clicked.connect(self._select_target_source_in_viewport)
        self.cloth.currentIndexChanged.connect(self._selection_changed)
        self.target.currentIndexChanged.connect(self._selection_changed)
        self.pins.editingFinished.connect(self._selection_changed)
        self.seams.editingFinished.connect(self._selection_changed)
        for widget in (
            self.iterations,
            self.timestep,
            self.gravity_x,
            self.gravity_y,
            self.gravity_z,
            self.collision_radius,
        ):
            widget.valueChanged.connect(self._parameters_changed)
        self.thickness.valueChanged.connect(self._collision_changed)
        self.deflection.valueChanged.connect(self._collision_changed)
        from freecad_cloth.common.UiDesign import apply_panel_style, set_status

        set_status(
            self.status,
            "Select a simulation scene or create one with Create Simulation.",
            state="info",
        )
        self._load_scene_values()
        self._refresh_viewport_actions()
        apply_panel_style(self.form)

    @staticmethod
    def _join(values):
        return ",".join(str(v) for v in values or [])

    @staticmethod
    def _double_box(low, high, value, decimals):
        _, _, _, QtWidgets = _modules()
        box = QtWidgets.QDoubleSpinBox()
        box.setRange(low, high)
        box.setDecimals(decimals)
        box.setValue(value)
        return box

    @staticmethod
    def _spin(low, high, value):
        _, _, _, QtWidgets = _modules()
        box = QtWidgets.QSpinBox()
        box.setRange(low, high)
        box.setValue(value)
        return box

    def _ensure_property(self, name, type_name, group, default):
        if self.scene is None or hasattr(self.scene, name):
            return
        self.scene.addProperty(type_name, name, group)
        setattr(self.scene, name, default)

    def _load_scene_values(self):
        if self.scene is None:
            return
        for name, type_name, default in (
            ("MaterialPreset", "App::PropertyString", "Cotton"),
            ("StretchCompliance", "App::PropertyFloat", 0.35),
            ("BendCompliance", "App::PropertyFloat", 0.20),
            ("ArealDensity", "App::PropertyFloat", 0.01),
        ):
            self._ensure_property(name, type_name, "Fabric", default)
        index = self.material.findText(str(getattr(self.scene, "MaterialPreset", "Cotton")))
        self.material.setCurrentIndex(max(index, 0))
        self.stretch.setValue(float(getattr(self.scene, "StretchCompliance", 0.35)))
        self.bend.setValue(float(getattr(self.scene, "BendCompliance", 0.20)))
        self.density.setValue(float(getattr(self.scene, "ArealDensity", 0.01)))
        self._refresh_status()

    def _populate_selection_lists(self):
        self.cloth.clear()
        self.target.clear()
        doc = self.App.ActiveDocument
        if doc is None:
            return
        targets = []
        for obj in doc.Objects:
            if (
                getattr(obj, "ClothMeshType", "")
                or getattr(obj, "PatternType", "") == "PatternPiece"
            ):
                self.cloth.addItem(obj.Label, obj.Name)
            if getattr(obj, "TargetType", "") in ("Mannequin", "FreeCAD Geometry") and hasattr(
                obj, "SourceObject"
            ):
                targets.append(obj)
        for obj in targets:
            source = getattr(obj, "SourceObject", None)
            label = obj.Label
            if source is not None:
                label = "{} — {}".format(label, getattr(source, "Label", source.Name))
            self.target.addItem(label, obj.Name)
        if self.scene is not None:
            for obj in getattr(self.scene, "ClothPieces", ()):
                index = self.cloth.findData(obj.Name)
                if index >= 0:
                    self.cloth.setCurrentIndex(index)
            selected = getattr(self.scene, "DrapeTarget", None)
            if selected is not None:
                index = self.target.findData(selected.Name)
                if index >= 0:
                    self.target.setCurrentIndex(index)

    def _selection_changed(self):
        self._refresh_viewport_actions()
        if self.scene is None:
            return
        if self.cloth.currentData():
            obj = self.scene.Document.getObject(self.cloth.currentData())
            if obj:
                self.scene.ClothPieces = [obj]
        if self.target.currentData():
            obj = self.scene.Document.getObject(self.target.currentData())
            if obj:
                self.scene.DrapeTarget = obj
        self.scene.PinSelection = [
            p.strip() for p in self.pins.text().replace(";", ",").split(",") if p.strip()
        ]
        self.scene.SeamSelection = [
            p.strip() for p in self.seams.text().replace(",", ";").split(";") if p.strip()
        ]
        self.scene.Document.recompute()
        self._refresh_viewport_actions()
        self._refresh_status()

    def _active_document_object(self, name: str) -> FreeCADDocumentObjectProtocol | None:
        """Resolve a selected scene object in the current FreeCAD document."""
        document = getattr(self.scene, "Document", None) or self.App.ActiveDocument
        if document is None or not name:
            return None
        try:
            return document.getObject(str(name))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None

    def _selected_cloth_object(self) -> FreeCADDocumentObjectProtocol | None:
        """Return the current cloth piece selected in the scene combo box."""
        return self._active_document_object(self.cloth.currentData())

    def _selected_target_source(self) -> FreeCADDocumentObjectProtocol | None:
        """Resolve the current Drape Target and its linked visible collision source."""
        target = self._active_document_object(self.target.currentData())
        return getattr(target, "SourceObject", None) if target is not None else None

    def _refresh_viewport_actions(self) -> None:
        """Enable viewport selection actions only when their objects are resolvable."""
        cloth_button = getattr(self, "cloth_view_button", None)
        if cloth_button is not None:
            cloth_button.setEnabled(self._selected_cloth_object() is not None)
        target_button = getattr(self, "target_view_button", None)
        if target_button is not None:
            target_button.setEnabled(self._selected_target_source() is not None)

    def _select_in_viewport(self, obj: FreeCADDocumentObjectProtocol | None, role: str) -> bool:
        """Highlight one selected scene object without changing the current camera.

        Args:
            obj: Native document object to select in FreeCAD's 3D view.
            role: Short user-facing description such as cloth or drape target.

        Returns:
            True when the object was selected, otherwise False.
        """
        from freecad_cloth.common.UiDesign import set_status

        if obj is None:
            set_status(
                self.status,
                f"Select a valid {role} object before highlighting it in the viewport.",
                state="warning",
            )
            return False
        try:
            self.Gui.Selection.clearSelection()
            self.Gui.Selection.addSelection(obj)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            set_status(
                self.status,
                f"Could not select the {role} object in the viewport — {exc}.",
                state="error",
            )
            return False
        label = str(getattr(obj, "Label", getattr(obj, "Name", role)))
        set_status(
            self.status,
            f"Selected {label} in the 3D view. The camera position is unchanged.",
            state="info",
        )
        return True

    def _select_cloth_in_viewport(self) -> bool:
        """Highlight the currently selected cloth object in the active 3D view."""
        return self._select_in_viewport(self._selected_cloth_object(), "cloth")

    def _select_target_source_in_viewport(self) -> bool:
        """Highlight the selected target's linked collision source in the active 3D view."""
        return self._select_in_viewport(self._selected_target_source(), "drape target source")

    def _material_changed(self, preset):
        if self.scene is None:
            return
        values = self.MATERIALS.get(str(preset), self.MATERIALS["Cotton"])
        self.stretch.setValue(values[0])
        self.bend.setValue(values[1])
        self.density.setValue(values[2])
        for name, type_name, default in (
            ("MaterialPreset", "App::PropertyString", "Cotton"),
            ("StretchCompliance", "App::PropertyFloat", 0.35),
            ("BendCompliance", "App::PropertyFloat", 0.20),
            ("ArealDensity", "App::PropertyFloat", 0.01),
        ):
            self._ensure_property(name, type_name, "Fabric", default)
        self.scene.MaterialPreset = str(preset)
        self.scene.StretchCompliance = values[0]
        self.scene.BendCompliance = values[1]
        self.scene.ArealDensity = values[2]
        self.scene.Document.recompute()

    def _parameters_changed(self):
        if self.scene is None:
            return
        self.scene.Iterations = self.iterations.value()
        self.scene.TimeStep = self.timestep.value()
        self.scene.GravityX = self.gravity_x.value()
        self.scene.GravityY = self.gravity_y.value()
        self.scene.GravityZ = self.gravity_z.value()
        self.scene.CollisionRadius = self.collision_radius.value()
        self.scene.Document.recompute()
        self._refresh_status()

    def _collision_changed(self):
        if self.scene is None:
            return
        target = getattr(self.scene, "DrapeTarget", None)
        if target is not None:
            target.CollisionThickness = self.thickness.value()
            target.CollisionDeflection = self.deflection.value()
        self.scene.Document.recompute()
        self._refresh_status()

    def _ensure_scene(self):
        if self.scene is None:
            from freecad_cloth.simulation.SimulationObjects import create_simulation_scene

            self.scene = create_simulation_scene(
                self.App.ActiveDocument or self.App.newDocument("ClothDrape")
            )
            self._populate_selection_lists()
            self._load_scene_values()
        self._parameters_changed()
        self._selection_changed()
        return self.scene

    def step(self, count: int) -> None:
        """Advance the active scene and refresh its visible simulation state.

        Args:
            count: Number of solver steps to execute.
        """
        scene = self._ensure_scene()
        scene.Steps = int(scene.Steps) + int(count)
        scene.Document.recompute()
        self.steps.setValue(int(scene.Steps))
        self._refresh_status()
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def reset(self) -> None:
        """Reset runtime state while retaining the selected cloth and drape target."""
        if self.scene is not None:
            from freecad_cloth.simulation.SimulationObjects import reset_scene

            reset_scene(self.scene)
        self.steps.setValue(0)
        self._refresh_status("Simulation reset; selections retained.")

    def _refresh_status(self, message=None):
        from freecad_cloth.common.UiDesign import set_status

        if self.scene is None:
            set_status(
                self.status,
                message or "Select a simulation scene or create one with Create Simulation.",
                state="warning",
            )
            return
        target_message = "No drape target selected"
        target_state = "missing"
        try:
            from freecad_cloth.simulation.DrapeTarget import target_status

            target_info = target_status(getattr(self.scene, "DrapeTarget", None))
            target_message = str(target_info["message"])
            target_state = str(target_info["state"])
        except (ImportError, AttributeError, TypeError, ValueError):
            target_state = "unavailable"
        finite_state = bool(getattr(self.scene, "FiniteState", True))
        simulation_state = "ready" if finite_state else "invalid/non-finite"
        status_message = message or "State: %s | Target: %s | %.3f s | %d particles | %d steps" % (
            simulation_state,
            target_message,
            float(getattr(self.scene, "SimulatedTime", 0.0)),
            int(getattr(self.scene, "ParticleCount", 0)),
            int(getattr(self.scene, "Steps", 0)),
        )
        if not finite_state:
            semantic_state = "error"
        elif target_state != "ready":
            semantic_state = "warning"
        else:
            semantic_state = "success"
        set_status(
            self.status,
            status_message,
            state="info" if message else semantic_state,
        )

    def accept(self) -> bool:
        """Commit current panel values to the active simulation document.

        Returns:
            True after the current panel values have been committed.
        """
        self._ensure_scene().Document.recompute()
        return True

    def reject(self) -> bool:
        """Close the task panel without changing its persisted selections.

        Returns:
            True after the task panel has closed or the close request was unnecessary.
        """
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog():
            self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self) -> int:
        """Return the native OK and Cancel buttons for FreeCAD's task-panel host.

        Returns:
            The combined Qt dialog-button flags requested by the workbench host.
        """
        _, _, _, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_simulation_task(scene=None):
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = SimulationTaskPanel(scene)
    Gui.Control.showDialog(panel)
    return panel

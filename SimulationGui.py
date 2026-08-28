"""FreeCAD GUI controls for the Cloth Simulation workbench."""

def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class SimulationTaskPanel:
    """Task panel exposing solver controls for a Cloth Simulation object."""
    def __init__(self, scene=None):
        App, Gui, QtWidgets = _modules()
        self.App, self.Gui, self.scene = App, Gui, scene
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)
        self.iterations = QtWidgets.QSpinBox(); self.iterations.setRange(1, 100); self.iterations.setValue(int(getattr(scene, 'Iterations', 8)))
        self.timestep = QtWidgets.QDoubleSpinBox(); self.timestep.setRange(0.0001, 1.0); self.timestep.setDecimals(5); self.timestep.setValue(float(getattr(scene, 'TimeStep', 1.0/60.0))); self.timestep.setSuffix(" s")
        self.gravity = QtWidgets.QDoubleSpinBox(); self.gravity.setRange(-50000, 50000); self.gravity.setDecimals(1); self.gravity.setValue(float(getattr(scene, 'GravityZ', -9810))); self.gravity.setSuffix(" mm/s²")
        self.steps = QtWidgets.QSpinBox(); self.steps.setRange(0, 100000); self.steps.setValue(int(getattr(scene, 'Steps', 0)))
        layout.addRow("Iterations", self.iterations); layout.addRow("Time step", self.timestep)
        layout.addRow("Gravity Z", self.gravity); layout.addRow("Simulation steps", self.steps)
        controls = QtWidgets.QHBoxLayout()
        self.step_button = QtWidgets.QPushButton("Step")
        self.run_button = QtWidgets.QPushButton("Run 30")
        self.reset_button = QtWidgets.QPushButton("Reset")
        controls.addWidget(self.step_button); controls.addWidget(self.run_button); controls.addWidget(self.reset_button)
        layout.addRow(controls)
        self.status = QtWidgets.QLabel("Select or create a simulation scene.")
        self.status.setWordWrap(True); layout.addRow(self.status)
        self.step_button.clicked.connect(lambda: self.step(1))
        self.run_button.clicked.connect(lambda: self.step(30))
        self.reset_button.clicked.connect(self.reset)

    def _ensure_scene(self):
        if self.scene is None:
            from SimulationObjects import create_simulation_scene
            doc = self.App.ActiveDocument or self.App.newDocument("ClothDrape")
            self.scene = create_simulation_scene(doc)
        self.scene.Iterations = self.iterations.value(); self.scene.TimeStep = self.timestep.value(); self.scene.GravityZ = self.gravity.value()
        return self.scene

    def step(self, count):
        scene = self._ensure_scene()
        scene.Steps = int(scene.Steps) + int(count)
        scene.Document.recompute()
        self.steps.setValue(int(scene.Steps))
        self.status.setText("Simulated %.3f s; %d particles; finite=%s" % (float(scene.SimulatedTime), int(scene.ParticleCount), bool(scene.FiniteState)))
        self.Gui.activeDocument().activeView().fitAll()

    def reset(self):
        if self.scene is not None:
            doc = self.scene.Document
            name = self.scene.Name
            doc.removeObject(name)
            doc.recompute()
        self.scene = None
        self.steps.setValue(0)
        self.status.setText("Simulation reset.")

    def accept(self):
        self._ensure_scene().Document.recompute(); return True

    def reject(self):
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


def show_simulation_task(scene=None):
    _App, Gui, _QtWidgets = _modules()
    panel = SimulationTaskPanel(scene)
    Gui.Control.showDialog(panel)
    return panel

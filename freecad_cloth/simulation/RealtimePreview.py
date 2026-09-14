"""Realtime viewport preview for cloth simulation.

The preview deliberately uses a coarse simulation mesh and a small XPBD iteration
budget. It is an interactive preview, not the authoritative final-quality solve.
"""

_PREVIEW = None


def _qt():
    try:
        from PySide import QtCore
    except ImportError:
        from PySide2 import QtCore
    return QtCore


def _scene():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        return None
    for obj in doc.Objects:
        if getattr(getattr(obj, "Proxy", None), "Type", "") == "ClothSimulation" or getattr(obj, "Name", "") == "ClothSimulation":
            return obj
    return None


def _prepare(scene):
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import ensure_quality_properties
    ensure_quality_properties(scene)
    # Interactive profile: coarse cloth + one solver iteration. The full-quality
    # properties are restored when playback stops, so the preview is disposable.
    ensure_quality_properties(scene)
    scene.QualityPreset = "Fast" if "Fast" in tuple(scene.QualityPreset) else scene.QualityPreset
    scene.ParticleDistance = max(24.0, float(scene.ParticleDistance))
    scene.SolverIterations = 2
    scene.SolverSubsteps = 1
    scene.TimeStep = 1.0 / 60.0
    scene.Steps = 0
    scene.Document.recompute()


class _Preview:
    def __init__(self, scene):
        QtCore = _qt()
        self.scene = scene
        self.timer = QtCore.QTimer()
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.running = False
        self._saved = {
            name: getattr(scene, name)
            for name in ("ParticleDistance", "SolverIterations", "SolverSubsteps", "TimeStep", "QualityPreset", "Steps")
            if hasattr(scene, name)
        }

    def start(self):
        if not self.running:
            self.running = True
            self.timer.start()
            self._message("Realtime preview running")

    def stop(self, restore=True):
        self.timer.stop()
        was_running = self.running
        self.running = False
        if restore and was_running:
            for name, value in self._saved.items():
                if hasattr(self.scene, name):
                    setattr(self.scene, name, value)
            self.scene.Document.recompute()
        self._message("Realtime preview stopped")

    def tick(self):
        if not self.scene or getattr(self.scene, "Document", None) is None:
            self.stop(False)
            return
        try:
            self.scene.Steps = int(self.scene.Steps) + 1
            self.scene.Document.recompute()
            gui = __import__("FreeCADGui")
            if gui.activeDocument():
                gui.activeDocument().activeView().redraw()
        except Exception as exc:
            self.stop(False)
            self._message("Realtime preview stopped: %s" % exc)

    @staticmethod
    def _message(text):
        try:
            import FreeCAD as App
            App.Console.PrintMessage("Cloth: %s\n" % text)
        except Exception:
            pass


def toggle_realtime_preview():
    global _PREVIEW
    scene = _scene()
    if scene is None:
        try:
            import FreeCADGui as Gui
            Gui.doCommand("from freecad_cloth.simulation.SimulationCommands import create_simulation")
            Gui.doCommand("create_simulation()")
        except Exception:
            pass
        scene = _scene()
    if scene is None:
        raise RuntimeError("Create a ClothSimulation scene first")
    if _PREVIEW is not None and _PREVIEW.running:
        _PREVIEW.stop()
        return False
    _prepare(scene)
    _PREVIEW = _Preview(scene)
    _PREVIEW.start()
    return True


def stop_realtime_preview():
    global _PREVIEW
    if _PREVIEW is not None:
        _PREVIEW.stop()
        _PREVIEW = None


def register_gui_command():
    try:
        import FreeCADGui as Gui
    except ImportError:
        return
    class _Command:
        def Activated(self):
            toggle_realtime_preview()
        def IsActive(self):
            return _scene() is not None
        def GetResources(self):
            return {"MenuText": "Realtime Cloth Preview", "ToolTip": "Play/pause a coarse cloth simulation in the FreeCAD viewport", "Pixmap": ""}
    if "ClothRealtimePreview" not in Gui.listCommands():
        Gui.addCommand("ClothRealtimePreview", _Command())


register_gui_command()

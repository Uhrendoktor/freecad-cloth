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
    # Interactive profile: very coarse cloth + one solver iteration. This is
    # deliberately game-style preview quality; final-quality solves are separate.
    try:
        scene.QualityPreset = "Fast"
    except (AttributeError, ValueError):
        pass
    scene.ParticleDistance = max(40.0, float(scene.ParticleDistance))
    scene.SolverIterations = 1
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
            for name in ("ParticleDistance", "SolverIterations", "SolverSubsteps", "TimeStep", "QualityPreset")
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
            # Recompute at zero steps so stopping never replays the preview at
            # final quality on the GUI thread.
            self.scene.Steps = 0
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
            import FreeCADGui as Gui
            if Gui.activeDocument():
                Gui.activeDocument().activeView().redraw()
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
        raise RuntimeError("Create a ClothSimulation scene first")
    if _PREVIEW is not None and _PREVIEW.running:
        _PREVIEW.stop()
        return False
    _PREVIEW = _Preview(scene)
    _prepare(scene)
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

"""Realtime viewport preview for the production Tissu simulation."""

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
    return next(
        (
            obj
            for obj in doc.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", "") == "ClothSimulation"
            or getattr(obj, "Name", "") == "ClothSimulation"
        ),
        None,
    )


def _prepare(scene):
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import ensure_quality_properties

    ensure_quality_properties(scene)
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = max(40.0, float(scene.ParticleDistance))
    scene.SolverIterations = 1
    scene.SolverSubsteps = 1
    scene.TimeStep = 1.0 / 60.0
    scene.Steps = 0
    scene.Document.recompute()
    proxy = getattr(scene, "Proxy", None)
    base = (
        proxy._base_or_restore()
        if proxy is not None and hasattr(proxy, "_base_or_restore")
        else proxy
    )
    if base is None or getattr(base, "backend", None) is None:
        raise RuntimeError("Realtime Cloth Preview did not build a simulation backend")
    if getattr(base.backend, "name", "") != "tissu":
        raise RuntimeError("Realtime Cloth Preview requires the Tissu backend")


class _Preview:
    """Own the interactive timer and restore the user's simulation quality settings."""

    def __init__(self, scene):
        QtCore = _qt()
        self.scene = scene
        self.timer = QtCore.QTimer()
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)
        self.running = False
        self._saved = {
            name: getattr(scene, name)
            for name in (
                "ParticleDistance",
                "SolverIterations",
                "SolverSubsteps",
                "TimeStep",
                "QualityPreset",
            )
            if hasattr(scene, name)
        }

    def start(self) -> None:
        """Start the preview timer."""
        if not self.running:
            self.running = True
            self.timer.start()
            self._message("Realtime preview running")

    def stop(self, restore: bool = True) -> None:
        """Stop the preview and optionally restore persistent quality settings."""
        self.timer.stop()
        was_running = self.running
        self.running = False
        if restore and was_running:
            try:
                self.scene.Steps = 0
                for name, value in self._saved.items():
                    if hasattr(self.scene, name):
                        setattr(self.scene, name, value)
                self.scene.Document.recompute()
            except ReferenceError:
                pass
        self._message("Realtime preview stopped")

    def tick(self) -> None:
        """Advance the persisted simulation step and redraw the viewport."""
        try:
            doc = getattr(self.scene, "Document", None)
            if doc is None:
                self.stop(False)
                return
            self.scene.Steps = int(self.scene.Steps) + 1
            doc.recompute()
            import FreeCADGui as Gui

            if Gui.activeDocument():
                Gui.activeDocument().activeView().redraw()
        except (ReferenceError, RuntimeError) as exc:
            self.stop(False)
            self._message(f"Realtime preview stopped: {exc}")
        except Exception as exc:
            self.stop(False)
            self._message(f"Realtime preview stopped: {exc}")

    @staticmethod
    def _message(message: str) -> None:
        try:
            import FreeCAD as App

            App.Console.PrintMessage(f"Cloth: {message}\n")
        except Exception:
            pass


def toggle_realtime_preview() -> bool:
    """Start or stop realtime preview and report whether it is running."""
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


def stop_realtime_preview() -> None:
    """Stop and discard the active preview controller."""
    global _PREVIEW
    if _PREVIEW is not None:
        _PREVIEW.stop()
        _PREVIEW = None


def register_gui_command() -> None:
    """Register the FreeCAD command once when the GUI runtime is available."""
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
            return {
                "MenuText": "Realtime Cloth Preview",
                "ToolTip": "Play/pause a coarse cloth simulation in the FreeCAD viewport",
                "Pixmap": "",
            }

    if "ClothRealtimePreview" not in Gui.listCommands():
        Gui.addCommand("ClothRealtimePreview", _Command())


register_gui_command()

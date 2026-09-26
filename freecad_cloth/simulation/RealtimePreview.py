"""Realtime viewport preview for cloth simulation.

The preview uses the selected cloth backend with a coarse interactive
simulation budget. It is an interactive preview, not the authoritative final-quality solve.
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
    _select_preview_backend(scene)


def _select_preview_backend(scene):
    """Replace the legacy XPBD backend with the explicitly selected backend.

    The base scene builder remains responsible for constructing the authoritative
    ClothSystem, panel topology, stitches, pins, and collision surface. The
    preview then wraps that exact state in Tissu when it is the preferred backend.
    """
    from freecad_cloth.simulation.ClothBackend import default_backend_registry, preferred_backend_name

    proxy = getattr(scene, "Proxy", None)
    base = proxy._base_or_restore() if proxy is not None and hasattr(proxy, "_base_or_restore") else proxy
    if base is None or getattr(base, "backend", None) is None:
        raise RuntimeError("Realtime Cloth Preview did not build a simulation backend")

    registry = default_backend_registry()
    backend_name = preferred_backend_name(registry)
    if backend_name == getattr(base.backend, "name", None):
        return base.backend
    if backend_name != "tissu":
        return base.backend

    system = getattr(base.backend, "system", None)
    if system is None:
        raise RuntimeError("Realtime Cloth Preview cannot transfer the simulation state to Tissu")
    triangles = tuple(
        tri
        for panel_triangles in getattr(base, "panel_triangles", {}).values()
        for tri in panel_triangles
    )
    pins = tuple(getattr(system, "pins", {}).keys())
    stitches = tuple((int(c.a), int(c.b)) for c in getattr(system, "stitches", ()))
    collision_surface = getattr(base, "collision_surface", None)
    if not triangles:
        raise RuntimeError("Realtime Cloth Preview did not build panel triangles")

    backend = registry.create(
        backend_name,
        system,
        triangles=triangles,
        pins=pins,
        stitches=stitches,
        collision_surface=collision_surface,
    )
    base.backend = backend
    base.last_steps = 0
    if proxy is not None and hasattr(proxy, "_sync_seam_stitch_provenance"):
        proxy._sync_seam_stitch_provenance(base)
    return backend


class _Preview:
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
            try:
                self.scene.Steps = 0
                for name, value in self._saved.items():
                    if hasattr(self.scene, name):
                        setattr(self.scene, name, value)
                self.scene.Document.recompute()
            except ReferenceError:
                pass
        self._message("Realtime preview stopped")

    def tick(self):
        scene = self.scene
        try:
            doc = getattr(scene, "Document", None)
            if doc is None:
                self.stop(False)
                return
            scene.Steps = int(scene.Steps) + 1
            doc.recompute()
            import FreeCADGui as Gui
            if Gui.activeDocument():
                Gui.activeDocument().activeView().redraw()
        except (ReferenceError, RuntimeError) as exc:
            self.stop(False)
            self._message("Realtime preview stopped: %s" % exc)
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

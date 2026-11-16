# Copyright (C) 2026 FreeCAD Cloth contributors
"""Realtime viewport preview for the production PositionBasedDynamics simulation."""

from __future__ import annotations

import time
from collections.abc import Sequence
from math import isfinite
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from freecad_cloth.simulation.RealtimeMeshPreview import RealtimeMeshPreview, _PreviewPanel
    from freecad_cloth.simulation.SimulationQualityRuntime import QualitySimulationProxy

_PREVIEW = None
_PREVIEW_TARGET_FPS = 60.0
_PREVIEW_FRAME_BUDGET_MS = 1000.0 / _PREVIEW_TARGET_FPS


def _next_timer_interval_ms(callback_elapsed_ms: float) -> int:
    """Return the remaining 60 FPS frame budget as a safe Qt timer interval.

    Args:
        callback_elapsed_ms: Time spent advancing and presenting the most recent frame.

    Returns:
        Millisecond delay that keeps callback time plus timer delay within the target
        frame budget when the callback itself fits the budget. A one millisecond
        minimum avoids a zero-interval timer starving the Qt event loop.
    """
    if not isfinite(callback_elapsed_ms):
        return 1
    remaining_ms = _PREVIEW_FRAME_BUDGET_MS - max(0.0, callback_elapsed_ms)
    return max(1, int(remaining_ms))


class _PreviewTimer(Protocol):
    """Expose the one-shot Qt timer operations used to schedule preview frames."""

    def setInterval(self, interval: int) -> None: ...

    def start(self) -> None: ...


def _schedule_next_frame(timer: _PreviewTimer, callback_elapsed_ms: float) -> None:
    """Schedule the next one-shot timer after the current frame has completed.

    Args:
        timer: Inactive single-shot Qt timer that owns the next preview callback.
        callback_elapsed_ms: Time spent advancing and presenting the current frame.
    """
    timer.setInterval(_next_timer_interval_ms(callback_elapsed_ms))
    timer.start()


class _SceneDocument(Protocol):
    def recompute(self) -> None: ...


class _SimulationScene(Protocol):
    QualityPreset: str
    ParticleDistance: float
    SolverIterations: int
    SolverSubsteps: int
    TimeStep: float
    Steps: int
    Document: _SceneDocument
    Proxy: object | None
    DrapePanels: Sequence[_PreviewPanel]
    FabricColor: Sequence[float]
    FabricTransparency: int
    FabricSpecular: float
    FabricRoughness: float


def _qt() -> ModuleType:
    if TYPE_CHECKING:
        from PySide2 import QtCore
    else:
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore
    return QtCore


def _scene() -> _SimulationScene | None:
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        return None
    scene = next(
        (
            obj
            for obj in doc.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", "") == "ClothSimulation"
            or getattr(obj, "Name", "") == "ClothSimulation"
        ),
        None,
    )
    return cast("_SimulationScene", scene) if scene is not None else None


def _prepare(scene: _SimulationScene) -> None:
    from freecad_cloth.simulation.SimulationQualityRuntime import ensure_quality_properties

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
        msg = "Realtime Cloth Preview did not build a simulation backend"
        raise RuntimeError(msg)
    if getattr(base.backend, "name", "") != "position-based-dynamics":
        msg = "Realtime Cloth Preview requires the PositionBasedDynamics backend"
        raise RuntimeError(msg)


class _Preview:
    """Own the interactive timer and restore the user's simulation quality settings."""

    def __init__(self, scene: _SimulationScene) -> None:
        QtCore = _qt()
        self.scene = scene
        self.timer = QtCore.QTimer()
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.running = False
        self._overlay_refresh_ticks = 0
        self._mesh_preview: RealtimeMeshPreview | None = None
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
        """Start the preview timer with transient viewport-only panel geometry."""
        if self.running:
            return
        from freecad_cloth.simulation.RealtimeMeshPreview import RealtimeMeshPreview, _Triangle

        proxy = self.scene.Proxy
        if proxy is None or not hasattr(proxy, "set_preview_mesh_publisher"):
            msg = "Realtime preview requires the quality-aware mesh publication path"
            raise RuntimeError(msg)
        quality_proxy = cast("QualitySimulationProxy", proxy)
        base = quality_proxy._base_or_restore()
        backend = getattr(base, "backend", None)
        if backend is None:
            msg = "Realtime preview requires an initialized solver backend"
            raise RuntimeError(msg)

        panels = cast("Sequence[_PreviewPanel]", self.scene.DrapePanels)
        panel_triangles = cast("dict[str, Sequence[_Triangle]]", base.panel_triangles)
        mesh_preview = RealtimeMeshPreview(
            panels,
            panel_triangles,
            self.scene.FabricColor,
            self.scene.FabricTransparency,
            self.scene.FabricSpecular,
            self.scene.FabricRoughness,
        )
        try:
            quality_proxy.set_preview_mesh_publisher(mesh_preview.publish)
            mesh_preview.publish_all(panels, backend.positions(), panel_triangles)
        except Exception:
            quality_proxy.set_preview_mesh_publisher(None)
            mesh_preview.close()
            raise
        self._mesh_preview = mesh_preview
        self.running = True
        self.timer.start()
        self._message("Realtime preview running")

    def stop(self, restore: bool = True) -> None:
        """Stop the preview, remove transient nodes and synchronize document meshes once."""
        self.timer.stop()
        was_running = self.running
        self.running = False
        proxy = self.scene.Proxy
        if proxy is not None and hasattr(proxy, "set_preview_mesh_publisher"):
            cast("QualitySimulationProxy", proxy).set_preview_mesh_publisher(None)
        mesh_preview = self._mesh_preview
        self._mesh_preview = None
        if mesh_preview is not None:
            mesh_preview.close()
        if was_running:
            try:
                if restore:
                    self.scene.Steps = 0
                    for name, value in self._saved.items():
                        if hasattr(self.scene, name):
                            setattr(self.scene, name, value)
                    self.scene.Document.recompute()
                elif proxy is not None and hasattr(proxy, "_publish_state"):
                    quality_proxy = cast("QualitySimulationProxy", proxy)
                    base = quality_proxy._base_or_restore()
                    quality_proxy._publish_state(self.scene, base)
            except (ReferenceError, RuntimeError):
                pass
        self._message("Realtime preview stopped")

    def tick(self) -> None:
        """Advance the persisted simulation step and redraw the viewport."""
        started_at = time.perf_counter()
        try:
            doc = getattr(self.scene, "Document", None)
            if doc is None:
                self.stop(False)
                return
            proxy = getattr(self.scene, "Proxy", None)
            if proxy is None or not hasattr(proxy, "advance_preview_frame"):
                msg = "Realtime Cloth Preview requires the recompute-free simulation path"
                raise RuntimeError(msg)
            proxy.advance_preview_frame(self.scene)
            self._overlay_refresh_ticks += 1
            if self._overlay_refresh_ticks % 2 == 0:
                from freecad_cloth.sewing.SeamOverlay import schedule_seam_overlay_refresh

                schedule_seam_overlay_refresh(doc)
            import FreeCADGui as Gui

            if Gui.activeDocument():
                Gui.activeDocument().activeView().redraw()
        except (ReferenceError, RuntimeError) as exc:
            self.stop(False)
            self._message(f"Realtime preview stopped: {exc}")
        except Exception as exc:
            self.stop(False)
            self._message(f"Realtime preview stopped: {exc}")
        finally:
            if self.running:
                callback_elapsed_ms = 1000.0 * (time.perf_counter() - started_at)
                _schedule_next_frame(self.timer, callback_elapsed_ms)

    @staticmethod
    def _message(message: str) -> None:
        try:
            import FreeCAD as App

            App.Console.PrintMessage(f"Cloth: {message}\n")
        except Exception:
            pass


def toggle_realtime_preview() -> bool:
    """Start or stop realtime preview and report whether it is running.

    Returns:
        True when a preview has been started, or False when an active preview was stopped.

    Raises:
        RuntimeError: If no persistent ClothSimulation scene is available."""
    global _PREVIEW
    scene = _scene()
    if scene is None:
        msg = "Create a ClothSimulation scene first"
        raise RuntimeError(msg)
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
        def Activated(self) -> None:
            toggle_realtime_preview()

        def IsActive(self) -> bool:
            return _scene() is not None

        def GetResources(self) -> dict[str, str]:
            return {
                "MenuText": "Realtime Cloth Preview",
                "ToolTip": "Play/pause a coarse cloth simulation in the FreeCAD viewport",
                "Pixmap": "",
            }

    add_command = getattr(Gui, "addCommand", None)
    list_commands = getattr(Gui, "listCommands", None)
    if callable(add_command) and (
        not callable(list_commands) or "ClothRealtimePreview" not in list_commands()
    ):
        add_command("ClothRealtimePreview", _Command())


register_gui_command()

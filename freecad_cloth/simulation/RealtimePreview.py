# Copyright (C) 2026 FreeCAD Cloth contributors
"""Realtime viewport preview for the production PositionBasedDynamics simulation."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from math import ceil, isfinite
from threading import Event, Lock, Thread, current_thread
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from freecad_cloth.simulation.RealtimeMeshPreview import RealtimeMeshPreview, _PreviewPanel
    from freecad_cloth.simulation.SimulationQualityRuntime import QualitySimulationProxy

_PREVIEW = None
_PREVIEW_TARGET_FPS = 60.0
_FRAME_CLOCK_LEAD_MS = 0.75
_FRAME_DISPATCH_SAMPLE_LIMIT = 120


class _PulseSignal(Protocol):
    """Expose the thread-safe Qt signal used to queue a frame onto the GUI thread."""

    def emit(self, _scheduled_at: float, _emitted_at: float) -> None: ...


class _FrameDispatcher(Protocol):
    """Retain the GUI-thread QObject that receives worker clock pulses."""

    pulse: _PulseSignal

    def set_callback(self, callback: Callable[[float, float], None]) -> None: ...


class _FrameClock:
    """Emit deadline-paced frame pulses without relying on Qt timer wakeup granularity."""

    def __init__(self, pulse: _PulseSignal, target_fps: float) -> None:
        """Initialize a coalescing monotonic clock.

        Args:
            pulse: Qt signal that queues a scheduled deadline onto the GUI thread.
            target_fps: Requested interactive frame rate.
        """
        if not isfinite(target_fps) or target_fps <= 0.0:
            msg = "preview frame-clock target FPS must be positive and finite"
            raise ValueError(msg)
        self._emit = pulse.emit
        self._period_s = 1.0 / float(target_fps)
        self._lead_s = min(_FRAME_CLOCK_LEAD_MS / 1000.0, self._period_s * 0.1)
        self._stop_event = Event()
        self._lock = Lock()
        self._pending = False
        self._signals_emitted = 0
        self._coalesced_pulses = 0
        self._missed_deadlines = 0
        self._worker_wakeup_lateness_ms: list[float] = []
        self._thread: Thread | None = None
        self.target_fps = float(target_fps)

    def start(self) -> None:
        """Start the monotonic worker clock with one frame of lead time."""
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            self._pending = False
            self._signals_emitted = 0
            self._coalesced_pulses = 0
            self._missed_deadlines = 0
            self._worker_wakeup_lateness_ms.clear()
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            name="FreeCADClothPreviewClock",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop and join the worker so no pulse can outlive the preview controller."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not current_thread():
            thread.join(timeout=1.0)
        if thread is None or not thread.is_alive():
            self._thread = None

    def consume_frame(self) -> None:
        """Allow the worker to queue one future frame after the GUI receives this pulse."""
        with self._lock:
            self._pending = False

    def request_frame(self, scheduled_at: float, emitted_at: float | None = None) -> bool:
        """Queue one frame and retain worker wake timing before GUI dispatch.

        Args:
            scheduled_at: Monotonic deadline associated with this frame pulse.
            emitted_at: Actual worker emission time, or the current time for direct tests.

        Returns:
            True when a signal was emitted, or False when an already-pending pulse
            coalesced this deadline.
        """
        actual_emission = time.perf_counter() if emitted_at is None else float(emitted_at)
        worker_lateness_ms = max(0.0, 1000.0 * (actual_emission - scheduled_at))
        with self._lock:
            self._worker_wakeup_lateness_ms.append(worker_lateness_ms)
            if len(self._worker_wakeup_lateness_ms) > _FRAME_DISPATCH_SAMPLE_LIMIT:
                del self._worker_wakeup_lateness_ms[0]
            if self._pending:
                self._coalesced_pulses += 1
                return False
            self._pending = True
            self._signals_emitted += 1
        try:
            self._emit(float(scheduled_at), actual_emission)
        except Exception:
            self.consume_frame()
            self._stop_event.set()
            raise
        return True

    def snapshot(self) -> dict[str, int | float | str]:
        """Return immutable scheduler metadata for independent benchmark validation."""
        with self._lock:
            return {
                "mode": "threaded-queued-deadline",
                "target_fps": self.target_fps,
                "signals_emitted": self._signals_emitted,
                "coalesced_pulses": self._coalesced_pulses,
                "missed_deadlines": self._missed_deadlines,
            }

    def worker_wakeup_metrics(self) -> dict[str, int | float]:
        """Summarize time spent waking the worker before it emits the GUI pulse."""
        with self._lock:
            samples = tuple(self._worker_wakeup_lateness_ms)
        if not samples:
            return {"samples": 0, "mean_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
        ordered = sorted(samples)
        percentile_index = min(len(ordered) - 1, max(0, ceil(len(ordered) * 0.95) - 1))
        return {
            "samples": len(ordered),
            "mean_ms": sum(ordered) / len(ordered),
            "p95_ms": ordered[percentile_index],
            "max_ms": ordered[-1],
        }

    def _run(self) -> None:
        """Wait on monotonic deadlines and skip missed periods rather than catch up."""
        period = self._period_s
        next_deadline = time.perf_counter() + period - self._lead_s
        while not self._stop_event.is_set():
            wait_s = max(0.0, next_deadline - time.perf_counter())
            if self._stop_event.wait(wait_s):
                return
            now = time.perf_counter()
            lateness = now - next_deadline
            if lateness >= period:
                skipped = int(lateness // period)
                with self._lock:
                    self._missed_deadlines += skipped
                next_deadline += skipped * period
            self.request_frame(next_deadline, now)
            next_deadline += period


def _make_frame_dispatcher(callback: Callable[[float, float], None]) -> _FrameDispatcher:
    """Create a QObject receiver whose queued slot always executes on the GUI thread.

    Args:
        callback: Preview callback receiving the deadline and worker emission timestamp.

    Returns:
        A Qt signal bridge retained by the preview controller.

    Raises:
        RuntimeError: If the active PySide binding does not expose signal/slot factories.
    """
    QtCore = _qt()
    signal_factory = getattr(QtCore, "Signal", None) or getattr(QtCore, "pyqtSignal", None)
    slot_factory = getattr(QtCore, "Slot", None) or getattr(QtCore, "pyqtSlot", None)
    if not callable(signal_factory) or not callable(slot_factory):
        msg = "Realtime preview requires Qt signal and slot support"
        raise RuntimeError(msg)

    class _Dispatcher(QtCore.QObject):
        """Bridge worker-thread clock pulses to a queued GUI-thread slot."""

        pulse = signal_factory(float, float)

        def __init__(self) -> None:
            super().__init__()
            self._callback = callback
            self.pulse.connect(self.dispatch, QtCore.Qt.QueuedConnection)

        @slot_factory(float, float)
        def dispatch(self, scheduled_at: float, emitted_at: float) -> None:
            self._callback(float(scheduled_at), float(emitted_at))

        def set_callback(self, next_callback: Callable[[float, float], None]) -> None:
            self._callback = next_callback

    return cast("_FrameDispatcher", _Dispatcher())


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
        self.scene = scene
        self._dispatcher = _make_frame_dispatcher(self.tick)
        self._frame_clock = _FrameClock(self._dispatcher.pulse, _PREVIEW_TARGET_FPS)
        self.running = False
        self._overlay_refresh_ticks = 0
        self._mesh_preview: RealtimeMeshPreview | None = None
        self._frame_dispatch_lateness_ms: list[float] = []
        self._gui_queue_dispatch_lateness_ms: list[float] = []
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
        self._frame_dispatch_lateness_ms.clear()
        self._gui_queue_dispatch_lateness_ms.clear()
        self.running = True
        self._frame_clock.start()
        self._message("Realtime preview running")

    def stop(self, restore: bool = True) -> None:
        """Stop the preview, remove transient nodes and synchronize document meshes once."""
        was_running = self.running
        self.running = False
        self._frame_clock.stop()
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

    def set_tick_callback(self, callback: Callable[[float, float], None]) -> None:
        """Replace the GUI-thread callback while retaining the queued signal receiver.

        Args:
            callback: Instrumented or production callback receiving scheduler timestamps.
        """
        self._dispatcher.set_callback(callback)

    def stop_frame_clock(self) -> None:
        """Stop frame delivery while leaving the preview scenegraph active."""
        self._frame_clock.stop()

    def frame_scheduler_metrics(self) -> dict[str, int | float | str]:
        """Return frame-clock counters for independent benchmark validation."""
        return self._frame_clock.snapshot()

    def frame_worker_wakeup_metrics(self) -> dict[str, int | float]:
        """Return worker timer wake timing separately from GUI queue delivery."""
        return self._frame_clock.worker_wakeup_metrics()

    def tick(
        self,
        scheduled_at: float | None = None,
        emitted_at: float | None = None,
    ) -> None:
        """Advance one preview step on the GUI thread and redraw the viewport.

        Args:
            scheduled_at: Worker deadline associated with this frame, when scheduled.
            emitted_at: Actual worker signal emission time, when scheduled.
        """
        self._frame_clock.consume_frame()
        started_at = time.perf_counter()
        if scheduled_at is not None:
            dispatch_lateness_ms = max(0.0, 1000.0 * (started_at - scheduled_at))
            self._frame_dispatch_lateness_ms.append(dispatch_lateness_ms)
            if len(self._frame_dispatch_lateness_ms) > _FRAME_DISPATCH_SAMPLE_LIMIT:
                del self._frame_dispatch_lateness_ms[0]
        if emitted_at is not None:
            queue_lateness_ms = max(0.0, 1000.0 * (started_at - emitted_at))
            self._gui_queue_dispatch_lateness_ms.append(queue_lateness_ms)
            if len(self._gui_queue_dispatch_lateness_ms) > _FRAME_DISPATCH_SAMPLE_LIMIT:
                del self._gui_queue_dispatch_lateness_ms[0]
        if not self.running:
            return
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

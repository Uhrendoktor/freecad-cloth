"""Reusable Qt input simulation and animated UI evidence capture for FreeCAD tests."""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any, Callable


def _qt_modules() -> tuple[Any, Any, Any, Any]:
    """Return the QtCore, QtGui, QtTest and QtWidgets modules available in FreeCAD."""
    try:
        from PySide import QtCore, QtGui, QtTest, QtWidgets
    except ImportError:
        try:
            from PySide2 import QtCore, QtGui, QtTest, QtWidgets
        except ImportError:
            from PySide6 import QtCore, QtGui, QtTest, QtWidgets
    return QtCore, QtGui, QtTest, QtWidgets


def focus_main_window(gui: Any, size: tuple[int, int] | None = None) -> Any:
    """Show and focus the FreeCAD main window before injecting GUI events."""
    _QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    window = gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    if size is not None:
        window.resize(int(size[0]), int(size[1]))
    window.show()
    if hasattr(window, "raise_"):
        window.raise_()
    if hasattr(window, "activateWindow"):
        window.activateWindow()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    QtTest.QTest.qWait(100)
    return window


def viewport_widget(gui: Any, view: Any | None = None) -> Any:
    """Find the Qt widget that owns the active FreeCAD 3D viewport."""
    _QtCore, _QtGui, _QtTest, QtWidgets = _qt_modules()
    window = gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    target_width = target_height = 0
    if view is not None:
        try:
            size = view.getSize()
            target_width, target_height = int(size[0]), int(size[1])
        except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
            pass

    candidates: list[tuple[float, Any, str, int, int]] = []
    for widget in window.findChildren(QtWidgets.QWidget):
        try:
            if not widget.isVisible() or not widget.isEnabled():
                continue
            width, height = int(widget.width()), int(widget.height())
            if width < 200 or height < 180:
                continue
            class_name = str(widget.metaObject().className()).lower()
            object_name = str(widget.objectName()).lower()
            label = class_name + " " + object_name
            class_score = 0.0
            if "soqtglwidget" in label or "qopenglwidget" in label:
                class_score = 5000.0
            elif "soqtrenderarea" in label or "renderarea" in label:
                class_score = 4200.0
            elif "view3dinventorviewer" in label:
                class_score = 2200.0
            elif "viewer" in label or "viewport" in label or "coin" in label:
                class_score = 1200.0
            size_delta = (
                abs(width - target_width) + abs(height - target_height)
                if target_width and target_height
                else 0
            )
            depth = 0
            parent = widget.parentWidget()
            while parent is not None:
                depth += 1
                parent = parent.parentWidget()
            # Prefer the innermost actual rendering surface, not its viewer
            # container: QtTest sends directly to the named widget and bypasses
            # the normal child-widget hit test when a parent is targeted.
            score = class_score + min(width * height / 100000.0, 20.0) - 4.0 * size_delta + min(depth, 12) * 2.0
            candidates.append((score, widget, label, width, height))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    if not candidates:
        raise RuntimeError("could not locate a visible FreeCAD viewport widget")
    candidates.sort(key=lambda item: item[0], reverse=True)
    top = candidates[:5]
    print(
        "freecad-input-viewport=" + repr([
            {"class": value[2], "size": (value[3], value[4]), "score": round(value[0], 1)}
            for value in top
        ]),
        flush=True,
    )
    if target_width and target_height:
        best_delta = abs(top[0][3] - target_width) + abs(top[0][4] - target_height)
        if best_delta > max(100, int((target_width + target_height) * 0.2)):
            raise RuntimeError(
                "selected Qt widget does not match FreeCAD viewport dimensions: "
                f"widget={top[0][3]}x{top[0][4]} view={target_width}x{target_height}"
            )
    return candidates[0][1]


def _position(QtCore: Any, position: tuple[float, float]) -> Any:
    """Convert a numeric viewport point to a Qt integer point."""
    return QtCore.QPoint(int(round(position[0])), int(round(position[1])))


def _button_and_modifiers(QtCore: Any, button: Any | None, modifiers: Any | None) -> tuple[Any, Any]:
    """Resolve default Qt mouse button and modifier values across Qt bindings."""
    resolved_button = getattr(QtCore.Qt, "LeftButton") if button is None else button
    resolved_modifiers = getattr(QtCore.Qt, "NoModifier") if modifiers is None else modifiers
    return resolved_button, resolved_modifiers


def mouse_press(
    widget: Any,
    position: tuple[float, float],
    button: Any | None = None,
    modifiers: Any | None = None,
    delay_ms: int = 20,
) -> None:
    """Inject a real Qt mouse-press event into a viewport or widget."""
    QtCore, _QtGui, QtTest, _QtWidgets = _qt_modules()
    resolved_button, resolved_modifiers = _button_and_modifiers(QtCore, button, modifiers)
    QtTest.QTest.mousePress(
        widget, resolved_button, resolved_modifiers, _position(QtCore, position), max(0, delay_ms)
    )


def mouse_move(
    widget: Any,
    position: tuple[float, float],
    delay_ms: int = 20,
    buttons_down: bool = False,
) -> None:
    """Move the pointer, optionally preserving the left-button-down drag state."""
    QtCore, QtGui, QtTest, QtWidgets = _qt_modules()
    local = _position(QtCore, position)
    if not buttons_down:
        QtTest.QTest.mouseMove(widget, local, max(0, delay_ms))
        return

    screen_position = widget.mapToGlobal(local)
    no_button = getattr(QtCore.Qt, "NoButton")
    left_button = getattr(QtCore.Qt, "LeftButton")
    no_modifier = getattr(QtCore.Qt, "NoModifier")
    event_type = QtCore.QEvent.MouseMove
    event = None
    try:
        event = QtGui.QMouseEvent(
            event_type,
            QtCore.QPointF(local),
            QtCore.QPointF(screen_position),
            no_button,
            left_button,
            no_modifier,
        )
    except TypeError:
        event = QtGui.QMouseEvent(
            event_type, QtCore.QPointF(local), no_button, left_button, no_modifier
        )
    QtWidgets.QApplication.sendEvent(widget, event)
    QtTest.QTest.qWait(max(0, delay_ms))


def mouse_release(
    widget: Any,
    position: tuple[float, float],
    button: Any | None = None,
    modifiers: Any | None = None,
    delay_ms: int = 20,
) -> None:
    """Inject a real Qt mouse-release event into a viewport or widget."""
    QtCore, _QtGui, QtTest, _QtWidgets = _qt_modules()
    resolved_button, resolved_modifiers = _button_and_modifiers(QtCore, button, modifiers)
    QtTest.QTest.mouseRelease(
        widget, resolved_button, resolved_modifiers, _position(QtCore, position), max(0, delay_ms)
    )


def click_viewport(
    widget: Any,
    position: tuple[float, float],
    gui: Any,
    additive: bool = False,
    button: Any | None = None,
) -> None:
    """Click a projected 3D point; additive clicks use Ctrl for multi-selection."""
    QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    resolved_button, _ = _button_and_modifiers(QtCore, button, None)
    modifiers = getattr(QtCore.Qt, "ControlModifier") if additive else getattr(QtCore.Qt, "NoModifier")
    QtTest.QTest.mouseClick(widget, resolved_button, modifiers, _position(QtCore, position), 20)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    gui.updateGui()
    QtTest.QTest.qWait(50)


def click_widget(widget: Any, button: Any | None = None, modifiers: Any | None = None) -> None:
    """Click a visible Qt control through QtTest rather than calling its slot directly."""
    QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    resolved_button, resolved_modifiers = _button_and_modifiers(QtCore, button, modifiers)
    if not widget.isVisible():
        raise RuntimeError("cannot click a hidden UI widget")
    QtTest.QTest.mouseClick(widget, resolved_button, resolved_modifiers, widget.rect().center(), 20)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    QtTest.QTest.qWait(50)


def drag_viewport(
    widget: Any,
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 16,
    duration_ms: int = 400,
    release: bool = True,
) -> None:
    """Simulate a pointer drag with intermediate move events and optional release."""
    if steps < 1:
        raise ValueError("a drag must contain at least one movement step")
    mouse_press(widget, start)
    delay = max(1, int(duration_ms / steps))
    for index in range(1, steps + 1):
        fraction = index / steps
        point = (
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
        )
        mouse_move(widget, point, delay_ms=delay, buttons_down=True)
    if release:
        mouse_release(widget, end)


def _resolve_key(QtCore: Any, key: Any) -> Any:
    """Accept a Qt key enum or a readable name such as Escape or Space."""
    if not isinstance(key, str):
        return key
    name = key if key.startswith("Key_") else "Key_" + key
    try:
        return getattr(QtCore.Qt, name)
    except AttributeError as exc:
        raise ValueError("unknown Qt keyboard key: " + key) from exc


def key_press(
    widget: Any,
    key: Any,
    modifiers: Any | None = None,
    delay_ms: int = 20,
) -> None:
    """Inject a keyboard press event into the focused widget."""
    QtCore, _QtGui, QtTest, _QtWidgets = _qt_modules()
    resolved_modifiers = getattr(QtCore.Qt, "NoModifier") if modifiers is None else modifiers
    QtTest.QTest.keyPress(widget, _resolve_key(QtCore, key), resolved_modifiers, max(0, delay_ms))


def key_release(
    widget: Any,
    key: Any,
    modifiers: Any | None = None,
    delay_ms: int = 20,
) -> None:
    """Inject a keyboard release event into the focused widget."""
    QtCore, _QtGui, QtTest, _QtWidgets = _qt_modules()
    resolved_modifiers = getattr(QtCore.Qt, "NoModifier") if modifiers is None else modifiers
    QtTest.QTest.keyRelease(widget, _resolve_key(QtCore, key), resolved_modifiers, max(0, delay_ms))


def key_click(
    widget: Any,
    key: Any,
    modifiers: Any | None = None,
    delay_ms: int = 20,
) -> None:
    """Send a complete keyboard interaction after explicitly focusing the target widget."""
    QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    if not widget.isVisible() or not widget.isEnabled():
        raise RuntimeError("cannot send keyboard input to a hidden or disabled widget")
    resolved_modifiers = getattr(QtCore.Qt, "NoModifier") if modifiers is None else modifiers
    widget.setFocus()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    QtTest.QTest.keyClick(
        widget, _resolve_key(QtCore, key), resolved_modifiers, max(0, delay_ms)
    )
    if app is not None:
        app.processEvents()
    QtTest.QTest.qWait(30)


def project_point(view: Any, point: Any) -> tuple[float, float]:
    """Project a FreeCAD world point to the viewport's top-left coordinate system."""
    projected = view.getPointOnScreen(point)
    size = view.getSize()
    return float(projected[0]), float(size[1] - projected[1])


def wait_until(
    predicate: Callable[[], bool],
    timeout_seconds: float = 3.0,
    description: str = "UI state",
) -> None:
    """Pump Qt events until an observable condition is true or time out."""
    _QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    deadline = time.monotonic() + float(timeout_seconds)
    app = QtWidgets.QApplication.instance()
    while time.monotonic() < deadline:
        if app is not None:
            app.processEvents()
        if predicate():
            return
        QtTest.QTest.qWait(25)
    raise TimeoutError("timed out waiting for " + description)


def write_gif(
    frames: list[Any],
    path: str | Path,
    fps: int = 7,
    max_colors: int = 96,
) -> Path:
    """Encode RGB Pillow frames as a compact infinitely looping animated GIF."""
    from PIL import Image

    if fps < 1 or fps > 30:
        raise ValueError("GIF frame rate must be between 1 and 30 FPS")
    if not frames:
        raise ValueError("at least one frame is required to export a GIF")
    if max_colors < 2 or max_colors > 256:
        raise ValueError("GIF palette size must be between 2 and 256 colors")
    if len(frames) < 2:
        frames = [frames[0], frames[0].copy()]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    adaptive = getattr(getattr(Image, "Palette", Image), "ADAPTIVE")
    converted = [
        frame.convert("RGB").convert("P", palette=adaptive, colors=max_colors)
        for frame in frames
    ]
    converted[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=converted[1:],
        duration=max(80, int(1000 / fps)),
        loop=0,
        optimize=True,
        disposal=2,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("GIF encoder did not create a non-empty output")
    return output


class UiGifRecorder:
    """Capture the full FreeCAD main window as a cursor-annotated animated GIF."""

    def __init__(
        self,
        path: str | Path,
        gui: Any,
        window: Any | None = None,
        fps: int = 7,
        scale: float = 0.5,
        max_frames: int = 120,
        show_cursor: bool = True,
    ) -> None:
        if fps < 1 or fps > 30:
            raise ValueError("GIF frame rate must be between 1 and 30 FPS")
        if not 0.2 <= scale <= 1.0:
            raise ValueError("GIF scale must be between 0.2 and 1.0")
        if max_frames < 2:
            raise ValueError("at least two GIF frames must be allowed")
        self.path = Path(path)
        self.gui = gui
        self.window = window
        self.fps = int(fps)
        self.scale = float(scale)
        self.max_frames = int(max_frames)
        self.show_cursor = bool(show_cursor)
        self.frames: list[Any] = []
        self._timer = None
        self._started = False

    def start(self) -> None:
        """Begin timer-driven capture of the active FreeCAD main window."""
        if self._started:
            raise RuntimeError("GIF recorder is already running")
        QtCore, _QtGui, _QtTest, QtWidgets = _qt_modules()
        app = QtWidgets.QApplication.instance()
        if app is None or app.primaryScreen() is None:
            raise RuntimeError("Qt screen capture is unavailable")
        if self.window is None:
            self.window = self.gui.getMainWindow()
        if self.window is None or not self.window.isVisible():
            raise RuntimeError("FreeCAD main window must be visible before recording")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.frames = []
        self._timer = QtCore.QTimer(app)
        self._timer.setInterval(max(20, int(1000 / self.fps)))
        self._timer.timeout.connect(self._capture_frame)
        self._started = True
        self.capture()
        self._timer.start()

    def _capture_frame(self) -> None:
        """Capture and downscale one window frame without re-entering the Qt event loop."""
        if not self._started or len(self.frames) >= self.max_frames:
            return
        QtCore, QtGui, _QtTest, QtWidgets = _qt_modules()
        from PIL import Image, ImageDraw

        app = QtWidgets.QApplication.instance()
        screen = None if app is None else app.primaryScreen()
        if screen is None or self.window is None:
            raise RuntimeError("FreeCAD main-window screenshot is unavailable")
        pixmap = screen.grabWindow(int(self.window.winId()))
        if pixmap.isNull():
            raise RuntimeError("Qt returned an empty FreeCAD main-window screenshot")
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        if not pixmap.save(buffer, "PNG"):
            buffer.close()
            raise RuntimeError("could not encode a UI frame as PNG")
        payload = bytes(buffer.data())
        buffer.close()
        frame = Image.open(io.BytesIO(payload)).convert("RGB")
        if self.show_cursor:
            cursor = QtGui.QCursor.pos()
            local = self.window.mapFromGlobal(cursor)
            x, y = int(local.x()), int(local.y())
            if 0 <= x < frame.width and 0 <= y < frame.height:
                draw = ImageDraw.Draw(frame)
                draw.ellipse(
                    (x - 9, y - 9, x + 9, y + 9),
                    fill=(255, 220, 0),
                    outline=(20, 20, 20),
                    width=3,
                )
                draw.ellipse(
                    (x - 3, y - 3, x + 3, y + 3),
                    fill=(230, 40, 40),
                    outline=(255, 255, 255),
                    width=1,
                )
        width = max(1, int(frame.width * self.scale))
        height = max(1, int(frame.height * self.scale))
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        if frame.size != (width, height):
            frame = frame.resize((width, height), resampling)
        self.frames.append(frame)

    def capture(self) -> None:
        """Capture an immediate frame after processing pending Qt paint events."""
        _QtCore, _QtGui, _QtTest, QtWidgets = _qt_modules()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.processEvents()
        self._capture_frame()

    def hold(self, milliseconds: int) -> None:
        """Keep the current visible state on screen long enough to read in the GIF."""
        if not self._started:
            raise RuntimeError("GIF recorder is not running")
        _QtCore, _QtGui, QtTest, _QtWidgets = _qt_modules()
        self.capture()
        QtTest.QTest.qWait(max(0, int(milliseconds)))
        self.capture()

    def stop(self) -> Path:
        """Stop recording and persist the animated GIF to its requested path."""
        if not self._started:
            raise RuntimeError("GIF recorder is not running")
        if self._timer is not None:
            self._timer.stop()
        self.capture()
        self._started = False
        return write_gif(self.frames, self.path, fps=self.fps)

    def __enter__(self) -> UiGifRecorder:
        """Start recording when used as a context manager."""
        self.start()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        """Persist collected frames on normal exit and best-effort preserve failures."""
        if self._started:
            self.stop()

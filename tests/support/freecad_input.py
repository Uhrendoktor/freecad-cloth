"""Reusable Qt input simulation and animated UI evidence capture for FreeCAD tests."""

from __future__ import annotations

import ctypes
import ctypes.util
import io
import os
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


class _NativeXInput:
    """Inject real X11 pointer events so native Coin draggers keep button state."""

    def __init__(self) -> None:
        x11_name = ctypes.util.find_library("X11") or "libX11.so.6"
        xtst_name = ctypes.util.find_library("Xtst") or "libXtst.so.6"
        try:
            self._x11 = ctypes.CDLL(x11_name)
            self._xtst = ctypes.CDLL(xtst_name)
        except OSError as exc:
            raise RuntimeError(
                "native viewport input requires libX11 and libXtst in the Xvfb environment"
            ) from exc

        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        display_name = os.environ.get("DISPLAY")
        self.display = self._x11.XOpenDisplay(
            None if not display_name else display_name.encode("utf-8")
        )
        if not self.display:
            raise RuntimeError("could not open the current X11 display for GUI input")

        self._x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
        self._x11.XDefaultScreen.restype = ctypes.c_int
        self.screen = int(self._x11.XDefaultScreen(self.display))
        self._x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._x11.XSync.restype = ctypes.c_int
        self._x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._x11.XKeysymToKeycode.restype = ctypes.c_uint
        self._xtst.XTestFakeMotionEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
        ]
        self._xtst.XTestFakeMotionEvent.restype = ctypes.c_int
        self._xtst.XTestFakeButtonEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        ]
        self._xtst.XTestFakeButtonEvent.restype = ctypes.c_int
        self._xtst.XTestFakeKeyEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        ]
        self._xtst.XTestFakeKeyEvent.restype = ctypes.c_int
        self.pressed_buttons: set[int] = set()

    def sync(self) -> None:
        """Flush native input and wait for the X server to process it."""
        self._x11.XSync(self.display, 0)

    def move_global(self, x: int, y: int) -> None:
        """Move the real X11 pointer to global screen coordinates."""
        if not self._xtst.XTestFakeMotionEvent(
            self.display, self.screen, int(x), int(y), 0
        ):
            raise RuntimeError("XTest could not inject a mouse-move event")
        self.sync()

    def button(self, number: int, pressed: bool) -> None:
        """Press or release one native X11 mouse button."""
        if not self._xtst.XTestFakeButtonEvent(
            self.display, int(number), int(bool(pressed)), 0
        ):
            raise RuntimeError("XTest could not inject a mouse-button event")
        if pressed:
            self.pressed_buttons.add(int(number))
        else:
            self.pressed_buttons.discard(int(number))
        self.sync()

    def key(self, keysym: int, pressed: bool) -> None:
        """Press or release one X11 keyboard keysym, used for modifier keys."""
        keycode = int(self._x11.XKeysymToKeycode(self.display, int(keysym)))
        if keycode == 0:
            raise RuntimeError("X11 could not resolve keyboard keysym " + hex(keysym))
        if not self._xtst.XTestFakeKeyEvent(
            self.display, keycode, int(bool(pressed)), 0
        ):
            raise RuntimeError("XTest could not inject a keyboard modifier event")
        self.sync()


_NATIVE_INPUT: _NativeXInput | None = None
_ACTIVE_MOUSE_MODIFIERS: list[int] = []


def _native_input() -> _NativeXInput:
    """Return the process-wide native pointer driver used by FreeCAD/Xvfb tests."""
    global _NATIVE_INPUT
    if _NATIVE_INPUT is None:
        _NATIVE_INPUT = _NativeXInput()
    return _NATIVE_INPUT


def _x_button_number(QtCore: Any, button: Any | None) -> int:
    """Map Qt mouse-button names to X11 physical button numbers."""
    if isinstance(button, str):
        name = button.upper()
        if name in {"BUTTON1", "LEFT"}:
            return 1
        if name in {"BUTTON2", "MIDDLE"}:
            return 2
        if name in {"BUTTON3", "RIGHT"}:
            return 3
    if button is None or button == getattr(QtCore.Qt, "LeftButton"):
        return 1
    if button == getattr(QtCore.Qt, "MiddleButton"):
        return 2
    if button == getattr(QtCore.Qt, "RightButton"):
        return 3
    raise ValueError("unsupported X11 mouse button: " + repr(button))


def _modifier_keysyms(QtCore: Any, modifiers: Any | None) -> list[int]:
    """Translate common Qt keyboard modifiers to X11 keysyms."""
    if modifiers is None:
        return []
    result: list[int] = []
    candidates = (
        ("ControlModifier", 0xFFE3),
        ("ShiftModifier", 0xFFE1),
        ("AltModifier", 0xFFE9),
        ("MetaModifier", 0xFFE7),
    )
    for name, keysym in candidates:
        flag = getattr(QtCore.Qt, name, None)
        if flag is None:
            continue
        try:
            active = bool(modifiers & flag)
        except TypeError:
            active = False
        if active:
            result.append(keysym)
    return result


def _global_position(widget: Any, position: tuple[float, float]) -> tuple[int, int]:
    """Convert local widget coordinates into real display-global coordinates."""
    QtCore, _QtGui, _QtTest, _QtWidgets = _qt_modules()
    point = widget.mapToGlobal(_position(QtCore, position))
    return int(point.x()), int(point.y())


def _wait_input(delay_ms: int) -> None:
    """Pump the Qt event loop after native input reaches the X server."""
    _QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    if delay_ms > 0:
        QtTest.QTest.qWait(int(delay_ms))
    if app is not None:
        app.processEvents()


def release_all_input() -> None:
    """Release any pointer buttons or modifiers left down by an interrupted test."""
    global _ACTIVE_MOUSE_MODIFIERS
    if _NATIVE_INPUT is None:
        return
    for number in tuple(_NATIVE_INPUT.pressed_buttons):
        try:
            _NATIVE_INPUT.button(number, False)
        except RuntimeError:
            pass
    for keysym in reversed(_ACTIVE_MOUSE_MODIFIERS):
        try:
            _NATIVE_INPUT.key(keysym, False)
        except RuntimeError:
            pass
    _ACTIVE_MOUSE_MODIFIERS = []


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
    """Inject a native X11 mouse press at a viewport or widget-local coordinate."""
    QtCore, _QtGui, _QtTest, _QtWidgets = _qt_modules()
    driver = _native_input()
    number = _x_button_number(QtCore, button)
    x, y = _global_position(widget, position)
    driver.move_global(x, y)
    global _ACTIVE_MOUSE_MODIFIERS
    _ACTIVE_MOUSE_MODIFIERS = _modifier_keysyms(QtCore, modifiers)
    for keysym in _ACTIVE_MOUSE_MODIFIERS:
        driver.key(keysym, True)
    driver.button(number, True)
    _wait_input(max(0, delay_ms))


def mouse_move(
    widget: Any,
    position: tuple[float, float],
    delay_ms: int = 20,
    buttons_down: bool = False,
) -> None:
    """Move the real pointer; XTest preserves any button held by the caller."""
    driver = _native_input()
    if buttons_down and 1 not in driver.pressed_buttons:
        raise RuntimeError("drag move requested without a preceding left-button press")
    x, y = _global_position(widget, position)
    driver.move_global(x, y)
    _wait_input(max(0, delay_ms))


def mouse_release(
    widget: Any,
    position: tuple[float, float],
    button: Any | None = None,
    modifiers: Any | None = None,
    delay_ms: int = 20,
) -> None:
    """Move to the release point, then emit a native X11 mouse release."""
    QtCore, _QtGui, _QtTest, _QtWidgets = _qt_modules()
    driver = _native_input()
    number = _x_button_number(QtCore, button)
    x, y = _global_position(widget, position)
    driver.move_global(x, y)
    driver.button(number, False)
    global _ACTIVE_MOUSE_MODIFIERS
    active_modifiers = _ACTIVE_MOUSE_MODIFIERS or _modifier_keysyms(QtCore, modifiers)
    for keysym in reversed(active_modifiers):
        driver.key(keysym, False)
    _ACTIVE_MOUSE_MODIFIERS = []
    _wait_input(max(0, delay_ms))


def click_viewport(
    widget: Any,
    position: tuple[float, float],
    gui: Any,
    additive: bool = False,
    button: Any | None = None,
) -> None:
    """Inject a native viewport click; use semantic selection APIs in unsupported Pivy builds."""
    QtCore, _QtGui, _QtTest, QtWidgets = _qt_modules()
    modifiers = getattr(QtCore.Qt, "ControlModifier") if additive else None
    mouse_press(widget, position, button=button, modifiers=modifiers)
    mouse_release(widget, position, button=button)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    gui.updateGui()
    _wait_input(50)


def click_widget(widget: Any, button: Any | None = None, modifiers: Any | None = None) -> None:
    """Click a visible Qt control through QtTest instead of calling its slot directly."""
    QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    if not widget.isVisible() or not widget.isEnabled():
        raise RuntimeError("cannot click a hidden or disabled UI widget")
    resolved_button, resolved_modifiers = _button_and_modifiers(QtCore, button, modifiers)
    QtTest.QTest.mouseClick(
        widget, resolved_button, resolved_modifiers, widget.rect().center(), 20
    )
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    QtTest.QTest.qWait(40)


def drag_viewport(
    widget: Any,
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 16,
    duration_ms: int = 400,
    release: bool = True,
) -> None:
    """Simulate a real pointer drag with intermediate native motion events."""
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


def type_text(
    widget: Any,
    text: str,
    *,
    replace_selection: bool = True,
    press_enter: bool = False,
    delay_ms: int = 15,
) -> None:
    """Type text using Qt keyboard events, optionally replacing the current value."""
    QtCore, _QtGui, QtTest, QtWidgets = _qt_modules()
    if not widget.isVisible() or not widget.isEnabled():
        raise RuntimeError("cannot type into a hidden or disabled UI widget")
    widget.setFocus()
    if replace_selection and hasattr(widget, "selectAll"):
        widget.selectAll()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    QtTest.QTest.keyClicks(
        widget, str(text), getattr(QtCore.Qt, "NoModifier"), max(0, delay_ms)
    )
    if press_enter:
        enter_key = getattr(QtCore.Qt, "Key_Enter", None)
        if enter_key is None:
            enter_key = getattr(QtCore.Qt, "Key_Return")
        QtTest.QTest.keyClick(widget, enter_key, delay=max(0, delay_ms))
    if app is not None:
        app.processEvents()
    QtTest.QTest.qWait(40)


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

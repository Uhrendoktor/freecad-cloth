"""Regression tests for the reusable UI GIF encoder."""

import pytest


def test_write_gif_emits_looping_animation(tmp_path):
    pytest.importorskip("PIL.Image")
    from PIL import Image, ImageSequence

    from tests.support.freecad_input import write_gif

    frames = [
        Image.new("RGB", (32, 24), (255, 20, 20)),
        Image.new("RGB", (32, 24), (20, 20, 255)),
        Image.new("RGB", (32, 24), (20, 255, 20)),
    ]
    path = write_gif(frames, tmp_path / "ui.gif", fps=5)
    assert path.is_file()
    with Image.open(path) as gif:
        assert gif.format == "GIF"
        assert gif.info.get("loop") == 0
        assert sum(1 for _ in ImageSequence.Iterator(gif)) == 3
        assert gif.size == (32, 24)


def test_write_gif_rejects_invalid_frame_rate(tmp_path):
    pytest.importorskip("PIL.Image")
    from PIL import Image

    from tests.support.freecad_input import write_gif

    with pytest.raises(ValueError, match="frame rate"):
        write_gif([Image.new("RGB", (4, 4))], tmp_path / "invalid.gif", fps=0)


def test_write_gif_rejects_empty_frames(tmp_path):
    pytest.importorskip("PIL.Image")
    from tests.support.freecad_input import write_gif

    with pytest.raises(ValueError, match="at least one frame"):
        write_gif([], tmp_path / "empty.gif")

def test_resolve_key_maps_names_and_preserves_qt_enums():
    from types import SimpleNamespace

    from tests.support.freecad_input import _resolve_key

    core = SimpleNamespace(Qt=SimpleNamespace(Key_Space=32, Key_Return=13))
    assert _resolve_key(core, "Space") == 32
    assert _resolve_key(core, "Key_Return") == 13
    assert _resolve_key(core, 27) == 27
    with pytest.raises(ValueError, match="unknown Qt keyboard key"):
        _resolve_key(core, "NotARealKey")


def test_native_key_click_focuses_x11_window_before_key_events(monkeypatch):
    from types import SimpleNamespace

    from tests.support import freecad_input

    events = []

    class Widget:
        focused = False

        def isVisible(self):
            return True

        def isEnabled(self):
            return True

        def window(self):
            return self

        def winId(self):
            return 42

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def setFocus(self, *_args):
            self.focused = True

        def hasFocus(self):
            return self.focused

    class Driver:
        def focus_window(self, window_id):
            events.append(("focus", window_id))

        def key(self, keysym, pressed):
            events.append(("key", keysym, pressed))

    app = SimpleNamespace(processEvents=lambda: None)
    qt_core = SimpleNamespace(Qt=SimpleNamespace(OtherFocusReason=1))
    qt_test = SimpleNamespace(QTest=SimpleNamespace(qWait=lambda _ms: None))
    qt_widgets = SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: app))
    driver = Driver()
    monkeypatch.setattr(
        freecad_input, "_qt_modules", lambda: (qt_core, None, qt_test, qt_widgets)
    )
    monkeypatch.setattr(freecad_input, "_native_input", lambda: driver)
    monkeypatch.setattr(freecad_input, "_wait_input", lambda _ms: None)

    freecad_input.native_key_click(Widget(), "Space")

    assert events == [
        ("focus", 42),
        ("key", 0x20, True),
        ("key", 0x20, False),
    ]

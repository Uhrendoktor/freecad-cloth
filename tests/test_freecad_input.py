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
    path = write_gif(frames, tmp_path / "ui.gif", fps=12)
    assert path.is_file()
    with Image.open(path) as gif:
        assert gif.format == "GIF"
        assert gif.info.get("loop") == 0
        assert sum(1 for _ in ImageSequence.Iterator(gif)) == 3
        assert gif.size == (32, 24)
        # GIF delays have centisecond precision; 12 FPS encodes to about 80 ms.
        durations = [frame.info["duration"] for frame in ImageSequence.Iterator(gif)]
        assert all(80 <= duration < 100 for duration in durations)


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


def test_visual_asset_inventory_has_live_ci_producers():
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    checker = root / "tools" / "ci" / "check_visual_asset_contract.py"
    env = os.environ.copy()
    env.update(
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": "refs/pull/1/merge",
            "VISUAL_PUBLISH_RESULT": "skipped",
        }
    )
    result = subprocess.run(
        [sys.executable, str(checker)],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "visual-asset-contract=passed documented_and_generated=32" in result.stdout

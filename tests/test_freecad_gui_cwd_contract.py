"""Static contract for neutral-cwd FreeCAD GUI launch boundaries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _job(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start + len(marker))
    return source[start:end]


def test_gui_turntable_launches_from_neutral_cwd():
    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    job = _job(source, "  gui-turntables:", "  gui-visual-examples:")
    assert '-v "$PWD:/workspace" -w /tmp "$FREECAD_IMAGE"' in job
    assert "/opt/freecad/AppRun /workspace/tests/freecad_avatar_screenshot.py" in job
    assert "/opt/freecad/AppRun /workspace/tests/freecad_simulation_turntable.py" in job


def test_blanket_visual_launches_from_neutral_cwd():
    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    job = _job(source, "  gui-visual-examples:", "  publish-readme-turntables:")
    assert '-v "$PWD:/workspace" -w /tmp "$FREECAD_IMAGE"' in job
    assert "/opt/freecad/AppRun /workspace/tests/freecad_visual_examples.py" in job


if __name__ == "__main__":
    test_gui_turntable_launches_from_neutral_cwd()
    test_blanket_visual_launches_from_neutral_cwd()

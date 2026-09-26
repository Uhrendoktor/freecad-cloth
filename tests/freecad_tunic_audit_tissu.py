"""Compatibility entry point for the Tissu tunic audit.

The canonical source owns arrangement, sewing, UI and evidence generation. The
runtime/backend selection is supplied by CI through CLOTH_SIMULATION_BACKEND.
Keeping this wrapper thin prevents a second, divergent tunic fixture.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "tests" / "freecad_screenshot_source.py"
source = source_path.read_text(encoding="utf-8")
exec(compile(source, str(source_path), "exec"), globals(), globals())

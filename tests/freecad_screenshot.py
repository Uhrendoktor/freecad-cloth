"""Legacy entry point for the tunic visual regression.

The authoritative implementation is tests/freecad_screenshot_source.py; this
wrapper remains for older callers without maintaining a divergent fixture.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "tests" / "freecad_screenshot_source.py"
source = source_path.read_text(encoding="utf-8")
exec(compile(source, str(source_path), "exec"), globals(), globals())

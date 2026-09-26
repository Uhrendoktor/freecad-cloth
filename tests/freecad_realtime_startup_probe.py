"""Diagnostic FreeCAD startup/import probe for CI lifecycle investigation."""
from pathlib import Path
import os

OUT = Path("/workspace/artifacts/freecad-realtime")
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "startup-probe.log"

def mark(value):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(value + "\n")
        handle.flush()

LOG.write_text("", encoding="utf-8")
mark("script-start")
import FreeCAD as App
mark("freecad-imported")
import FreeCADGui as Gui
mark("freecadgui-imported")
from freecad_cloth.simulation import RealtimePreview
mark("realtime-preview-imported")
os._exit(0)

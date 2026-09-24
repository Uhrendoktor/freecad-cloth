"""Temporary CI probe for the FreeCAD 1.1 startup boundary.

This file is diagnostic only and is removed before release integration.
"""
import os
from pathlib import Path

root = Path(os.environ["FREECAD_PROBE_MARKER_DIR"])
case = os.environ["FREECAD_PROBE_CASE"]

def mark(stage: str) -> None:
    (root / (case + ".marker")).write_text(stage + "\n", encoding="utf-8")
    print("probe=" + case + ":" + stage, flush=True)

mark("script-loaded")

import FreeCAD as App  # noqa: E402
mark("freecad-imported")
import FreeCADGui as Gui  # noqa: E402
mark("freecadgui-imported")
import Part  # noqa: E402
mark("part-imported")

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

app = QtWidgets.QApplication.instance()
if app is not None:
    app.quit()
mark("quit-requested")

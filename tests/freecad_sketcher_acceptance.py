"""Canonical FreeCAD/Xvfb acceptance for native Sketcher pattern authoring."""
import math
import os
import tempfile
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()




def _record(message):
    print("sketcher-acceptance=%s" % message, flush=True)

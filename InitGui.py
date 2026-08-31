"""FreeCAD GUI entry point.

FreeCAD requires ``InitGui.py`` at the workbench root when the repository is
installed directly as a Mod. The implementation lives in the Python package so
normal tooling, tests, and future workbench packaging share the same code.
"""
from pathlib import Path

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

# Install the target execute/recompute guard before GUI workbench activation.
try:
    import DrapeTarget  # noqa: F401
except ImportError:
    pass

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import (
    COMMAND_GROUPS as SEWING_COMMAND_GROUPS,
    TOOLBAR_COMMANDS as SEWING_TOOLBAR_COMMANDS,
    ClothSewingWorkbench,
)
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"

if Gui is not None:
    Gui.addIconPath(str(_ICON_DIR))
    Gui.addWorkbench(ClothPatternWorkbench())
    Gui.addWorkbench(ClothSimulationWorkbench())
    Gui.addWorkbench(ClothSewingWorkbench())

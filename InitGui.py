"""FreeCAD GUI bootstrap entry point.

FreeCAD requires ``InitGui.py`` at the workbench root when the repository is
installed directly as a Mod. All workbench implementation remains under the
``freecad_cloth`` package tree.
"""

from pathlib import Path

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None
from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import ClothSewingWorkbench
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"

if Gui is not None:
    Gui.addIconPath(str(_ICON_DIR))
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        Gui.addWorkbench(ClothPatternWorkbench())
    if "ClothSimulationWorkbench" not in Gui.listWorkbenches():
        Gui.addWorkbench(ClothSimulationWorkbench())
    if "ClothSewingWorkbench" not in Gui.listWorkbenches():
        Gui.addWorkbench(ClothSewingWorkbench())

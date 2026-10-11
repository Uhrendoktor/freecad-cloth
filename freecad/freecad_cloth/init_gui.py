"""FreeCAD 1.1 GUI entry point for FreeCAD Cloth."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

import FreeCADGui as Gui

from freecad_cloth.pattern.workbench import ClothPatternWorkbench
from freecad_cloth.sewing.workbench import ClothSewingWorkbench
from freecad_cloth.simulation.workbench import ClothSimulationWorkbench

ICON_DIR = ROOT / "resources" / "icons"
if ICON_DIR.is_dir():
    Gui.addIconPath(str(ICON_DIR))

if "ClothPatternWorkbench" not in Gui.listWorkbenches():
    Gui.addWorkbench(ClothPatternWorkbench())
if "ClothSimulationWorkbench" not in Gui.listWorkbenches():
    Gui.addWorkbench(ClothSimulationWorkbench())
if "ClothSewingWorkbench" not in Gui.listWorkbenches():
    Gui.addWorkbench(ClothSewingWorkbench())

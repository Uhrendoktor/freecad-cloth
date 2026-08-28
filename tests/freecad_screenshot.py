"""Deterministic GUI documentation scenario; run under Xvfb with FreeCAD."""
import os
import FreeCAD as App
import FreeCADGui as Gui

import InitGui  # noqa: F401
from PatternCommands import create_pattern_piece_from_parameters
from PatternGui import show_pattern_piece_task
from SimulationObjects import create_drape_scene
from SimulationGui import show_simulation_task

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)

Gui.showMainWindow()
doc = App.newDocument("ClothDocumentation")
Gui.activateWorkbench("Cloth Pattern")
front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
back.Placement.Base.x = 170.0
doc.recompute()
Gui.activeDocument().activeView().viewTop()
Gui.activeDocument().activeView().fitAll()
show_pattern_piece_task(front)
Gui.updateGui()
Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "cloth-pattern.png"), 1280, 720, "Current", 1)
Gui.Control.closeDialog()

Gui.activateWorkbench("Cloth Simulation")
scene = create_drape_scene(doc)
doc.recompute()
Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
show_simulation_task(scene)
Gui.updateGui()
Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "cloth-simulation.png"), 1280, 720, "Current", 1)
Gui.Control.closeDialog()

print("generated", os.path.join(OUT, "cloth-pattern.png"), flush=True)
print("generated", os.path.join(OUT, "cloth-simulation.png"), flush=True)
doc.close()
try:
    Gui.getMainWindow().close()
except Exception:
    pass

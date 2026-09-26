"""Simulation workbench registration facade.

Command implementations remain in the package tree; this module owns the
FreeCAD workbench boundary and resolves its icon to the installed root resource.
"""
import os
from pathlib import Path

from freecad_cloth.gui import ClothWorkbenchBase


class ClothSimulationWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"

    def __init__(self):
        super().__init__()
        self.Icon = str(Path(__file__).resolve().parents[2] / "resources" / "icons" / "ClothSimulation.svg")

    def Activated(self):
        import FreeCAD as App
        import freecad_cloth.simulation.DrapeCommands as DrapeCommands
        from freecad_cloth.sewing.SewingView import apply_seam_colors
        DrapeCommands.register_gui_commands()
        if App.ActiveDocument is not None:
            apply_seam_colors(App.ActiveDocument.Objects)

    def Initialize(self):
        if self.commands:
            return
        os.environ.setdefault("CLOTH_SIMULATION_BACKEND", "tissu")
        import freecad_cloth.simulation.SimulationCommands as SimulationCommands
        import freecad_cloth.simulation.DrapeCommands as DrapeCommands
        import freecad_cloth.simulation.RealtimePreview as RealtimePreview
        DrapeCommands.register_gui_commands()
        self.register((("Simulation", SimulationCommands.COMMANDS + ["ClothRealtimePreview"] + DrapeCommands.COMMANDS),))

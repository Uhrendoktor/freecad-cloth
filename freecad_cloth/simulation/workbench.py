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
        super().Activated()
        import freecad_cloth.simulation.DrapeCommands as DrapeCommands
        DrapeCommands.register_gui_commands()

    def Initialize(self):
        if self.commands:
            return
        os.environ.setdefault("CLOTH_SIMULATION_BACKEND", "tissu")
        import freecad_cloth.simulation.SimulationCommands as SimulationCommands
        import freecad_cloth.simulation.DrapeCommands as DrapeCommands
        import freecad_cloth.simulation.RealtimePreview as RealtimePreview
        DrapeCommands.register_gui_commands()
        self.register((("Simulation", SimulationCommands.COMMANDS + ["ClothRealtimePreview"] + DrapeCommands.COMMANDS),))

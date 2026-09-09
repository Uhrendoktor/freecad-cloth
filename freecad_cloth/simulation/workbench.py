"""Simulation workbench registration facade.

Command implementations remain in the package tree; this module owns the
FreeCAD workbench boundary and resolves its icon to the installed root resource.
"""
from pathlib import Path

from freecad_cloth.gui import ClothWorkbenchBase


class ClothSimulationWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"

    def __init__(self):
        super().__init__()
        self.Icon = str(Path(__file__).resolve().parents[2] / "resources" / "icons" / "ClothSimulation.svg")

    def Initialize(self):
        if self.commands:
            return
        import freecad_cloth.simulation.SimulationCommands as SimulationCommands
        import freecad_cloth.simulation.DrapeCommands as DrapeCommands
        self.register((("Simulation", SimulationCommands.COMMANDS + DrapeCommands.COMMANDS),))

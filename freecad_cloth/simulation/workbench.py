"""Simulation workbench registration facade."""
from freecad_cloth.gui import ClothWorkbenchBase


class ClothSimulationWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"
    Icon = "ClothSimulation.svg"

    def Initialize(self):
        if self.commands:
            return
        import freecad_cloth.simulation.SimulationCommands
        import freecad_cloth.simulation.DrapeCommands
        self.register((("Simulation", SimulationCommands.COMMANDS + DrapeCommands.COMMANDS),))

"""Pattern workbench registration facade.

Command implementations remain in the package tree; this module owns the
FreeCAD workbench boundary and resolves its icon to the installed root resource.
"""
from pathlib import Path

from freecad_cloth.gui import ClothWorkbenchBase


class ClothPatternWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Pattern"
    ToolTip = "Parametric sewing-pattern design"

    def __init__(self):
        super().__init__()
        self.Icon = str(Path(__file__).resolve().parents[2] / "resources" / "icons" / "ClothPattern.svg")

    def Initialize(self):
        if self.commands:
            return
        import freecad_cloth.pattern.PatternCommands as PatternCommands
        import freecad_cloth.pattern.PatternMarks as PatternMarks
        self.register((("Pattern", PatternCommands.COMMANDS + PatternMarks.COMMANDS),))

"""Pattern workbench registration facade.

Command implementations remain in their compatibility modules until the
migration is complete; this module owns the workbench boundary.
"""
from freecad_cloth.gui import ClothWorkbenchBase


class ClothPatternWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Pattern"
    ToolTip = "Parametric sewing-pattern design"
    Icon = "ClothPattern.svg"

    def Initialize(self):
        if self.commands:
            return
        import freecad_cloth.pattern.PatternCommands
        import freecad_cloth.pattern.PatternMarks
        self.register((("Pattern", PatternCommands.COMMANDS + PatternMarks.COMMANDS),))

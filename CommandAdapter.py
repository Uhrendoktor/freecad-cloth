"""Small headless-safe adapter for FreeCAD GUI command registration."""


class FunctionCommand:
    """Expose a Python callable through FreeCAD's command protocol."""
    def __init__(self, function, tooltip=None):
        self.function = function
        self.tooltip = tooltip
    def Activated(self):
        return self.function()
    def GetResources(self):
        return {"MenuText": self.function.__name__.replace("_", " ").title(), "ToolTip": self.tooltip or self.function.__doc__ or "Cloth command"}


def register_commands(gui, commands):
    """Register ``name -> callable`` pairs without importing FreeCAD or Qt."""
    if not hasattr(gui, "addCommand"):
        return
    for name, function in commands.items():
        gui.addCommand(name, FunctionCommand(function))

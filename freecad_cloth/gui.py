"""Shared GUI registration primitives.

This module intentionally imports FreeCAD lazily so packaging/build metadata and
non-GUI tests can import the package outside a FreeCAD process.
"""

try:
    import FreeCADGui as Gui
except ImportError:  # pragma: no cover - exercised outside FreeCAD
    Gui = None


class ClothWorkbenchBase(Gui.Workbench if Gui is not None else object):
    """Small common registration shell for all Cloth workbenches."""

    def __init__(self):
        if Gui is not None:
            super().__init__()
        self.commands = []

    @staticmethod
    def normalize_commands(commands):
        return list(dict.fromkeys(str(c) for c in commands if str(c)))

    # Compatibility aliases retained while top-level InitGui.py migrates to the
    # package boundary. Existing tests and third-party scripts may use these
    # historical private names; removing them is a separate API migration.
    @staticmethod
    def _normalize_commands(commands):
        return ClothWorkbenchBase.normalize_commands(commands)

    def _register(self, commands):
        self._register_groups(((self.MenuText, commands),))

    def _register_groups(self, groups, toolbar_name=None, toolbar_commands=None):
        if self.commands:
            return
        normalized = []
        seen = []
        for group_name, commands in groups:
            group_commands = self.normalize_commands(commands)
            duplicates = [c for c in group_commands if c in seen]
            if duplicates:
                raise ValueError("commands registered in multiple groups: %s" % ", ".join(duplicates))
            if group_name and group_commands:
                normalized.append((str(group_name), group_commands))
                seen.extend(group_commands)
        self.commands = [c for _, commands in normalized for c in commands]
        if Gui is None:
            return
        if toolbar_name:
            toolbar = self.normalize_commands(toolbar_commands or self.commands)
            self.appendToolbar(toolbar_name, toolbar)
        else:
            for group_name, commands in normalized:
                self.appendToolbar(group_name, commands)
        for group_name, commands in normalized:
            self.appendMenu([self.MenuText, group_name], commands)

    def register(self, groups, toolbar_name=None, toolbar_commands=None):
        self._register_groups(groups, toolbar_name=toolbar_name, toolbar_commands=toolbar_commands)

    def GetResources(self):
        return {"MenuText": self.MenuText, "ToolTip": self.ToolTip, "Icon": self.Icon}

    def Activated(self):
        return None

    def Deactivated(self):
        return None

    def ContextMenu(self, recipient):
        if Gui is not None and recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"

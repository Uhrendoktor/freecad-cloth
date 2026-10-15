"""Shared GUI registration primitives and bootstrap for the FreeCAD loaders.

This module intentionally imports FreeCAD lazily so packaging/build metadata and
non-GUI tests can import the package outside a FreeCAD process.
"""

from collections.abc import Callable
from pathlib import Path

try:
    import FreeCADGui as Gui
except ImportError:  # pragma: no cover - exercised outside FreeCAD
    Gui = None


_WORKBENCH_DEACTIVATION_CALLBACK: Callable[[], None] | None = None


def register_workbench_deactivation_callback(
    callback: Callable[[], None] | None,
) -> None:
    """Register optional transient cleanup without coupling the base GUI to a workbench."""
    global _WORKBENCH_DEACTIVATION_CALLBACK
    _WORKBENCH_DEACTIVATION_CALLBACK = callback


def initialize_workbenches(installation_root: Path) -> None:
    """Register the Cloth workbenches from either supported FreeCAD loader layout."""
    if Gui is None:
        return

    icon_dir = Path(installation_root).resolve() / "resources" / "icons"
    if icon_dir.is_dir():
        Gui.addIconPath(str(icon_dir))

    from freecad_cloth.avatar import AvatarCommands
    from freecad_cloth.pattern.workbench import ClothPatternWorkbench
    from freecad_cloth.sewing.workbench import ClothSewingWorkbench
    from freecad_cloth.simulation.workbench import (
        AVATAR_ENTRY_COMMANDS,
        ClothSimulationWorkbench,
    )

    if not set(AVATAR_ENTRY_COMMANDS).issubset(AvatarCommands.COMMANDS):
        raise RuntimeError("Cloth Simulation avatar menu references unregistered commands")

    workbenches = (
        ("ClothPatternWorkbench", ClothPatternWorkbench),
        ("ClothSimulationWorkbench", ClothSimulationWorkbench),
        ("ClothSewingWorkbench", ClothSewingWorkbench),
    )
    registered = set(Gui.listWorkbenches())
    for workbench_name, workbench_type in workbenches:
        if workbench_name not in registered:
            Gui.addWorkbench(workbench_type())
            registered.add(workbench_name)


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
                raise ValueError(
                    "commands registered in multiple groups: {}".format(", ".join(duplicates))
                )
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
        callback = _WORKBENCH_DEACTIVATION_CALLBACK
        if callback is not None:

            def finish_deactivation() -> None:
                # FreeCAD may deliver the new workbench's Activated() before
                # the previous workbench's Deactivated(). Defer cleanup until
                # the transition settles so a Cloth-to-Cloth switch does not
                # disable the overlay that the incoming workbench just enabled.
                if Gui is not None:
                    try:
                        active = Gui.activeWorkbench()
                        active_name = str(active.name()).lower()
                    except (AttributeError, RuntimeError, TypeError):
                        active_name = ""
                    if active_name.startswith("cloth"):
                        return
                try:
                    callback()
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    pass

            try:
                try:
                    from PySide import QtCore
                except ImportError:
                    from PySide2 import QtCore
                QtCore.QTimer.singleShot(0, finish_deactivation)
            except ImportError:
                finish_deactivation()
        return

    def ContextMenu(self, recipient):
        if Gui is not None and recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"

"""Shared GUI registration primitives.

This module intentionally imports FreeCAD lazily so packaging/build metadata and
non-GUI tests can import the package outside a FreeCAD process.
"""

from collections.abc import Callable
from typing import Protocol, cast

try:
    import FreeCADGui as Gui
except ImportError:  # pragma: no cover - exercised outside FreeCAD
    Gui = None


class _ActiveWorkbench(Protocol):
    def name(self) -> str: ...


class _WorkbenchGui(Protocol):
    def activeWorkbench(self) -> _ActiveWorkbench: ...


_WORKBENCH_DEACTIVATION_CALLBACK: Callable[[], None] | None = None


def register_workbench_deactivation_callback(
    callback: Callable[[], None] | None,
) -> None:
    """Register optional transient cleanup without coupling the base GUI to a workbench."""
    global _WORKBENCH_DEACTIVATION_CALLBACK
    _WORKBENCH_DEACTIVATION_CALLBACK = callback


class ClothWorkbenchBase(Gui.Workbench if Gui is not None else object):
    """Small common registration shell for all Cloth workbenches."""

    def __init__(
        self,
        *,
        gui: object | None = None,
        toolbar_sink: Callable[..., object] | None = None,
        menu_sink: Callable[..., object] | None = None,
    ):
        if Gui is not None:
            super().__init__()
        self._gui = cast(_WorkbenchGui | None, Gui if gui is None else gui)
        self._toolbar_sink = toolbar_sink
        self._menu_sink = menu_sink
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
        if self._gui is None:
            return
        add_toolbar = self.appendToolbar if self._toolbar_sink is None else self._toolbar_sink
        add_menu = self.appendMenu if self._menu_sink is None else self._menu_sink
        if toolbar_name:
            toolbar = self.normalize_commands(toolbar_commands or self.commands)
            add_toolbar(toolbar_name, toolbar)
        else:
            for group_name, commands in normalized:
                add_toolbar(group_name, commands)
        for group_name, commands in normalized:
            add_menu([self.MenuText, group_name], commands)

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
                if self._gui is not None:
                    try:
                        active = self._gui.activeWorkbench()
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
        if self._gui is not None and recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"

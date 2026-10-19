# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared GUI registration primitives.

This module intentionally imports FreeCAD lazily so packaging/build metadata and
non-GUI tests can import the package outside a FreeCAD process.
"""

import importlib
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol, cast

try:
    import FreeCADGui as Gui
except ImportError:  # pragma: no cover - exercised outside FreeCAD
    Gui = None


class _ActiveWorkbench(Protocol):
    """Describe the workbench information queried during a GUI transition."""

    def name(self) -> str:
        """Return the name FreeCAD reports for this workbench."""


class _WorkbenchGui(Protocol):
    """Describe the subset of the FreeCAD GUI API used for transition checks."""

    def active_workbench(self) -> _ActiveWorkbench:
        """Return the workbench currently active in the FreeCAD GUI."""


@dataclass(slots=True)
class _WorkbenchDeactivationState:
    """Hold the optional transient-cleanup callback without module rebinding."""

    callback: Callable[[], None] | None = None


_WORKBENCH_DEACTIVATION_STATE = _WorkbenchDeactivationState()


def register_workbench_deactivation_callback(
    callback: Callable[[], None] | None,
) -> None:
    """Register optional transient cleanup without coupling the base GUI to a workbench.

    Args:
        callback: Cleanup function to run after leaving a non-Cloth workbench, or None
            to unregister the current callback.
    """
    _WORKBENCH_DEACTIVATION_STATE.callback = callback


def _defer_workbench_transition(callback: Callable[[], None]) -> None:
    """Schedule a callback after the current GUI event, if Qt is available.

    Args:
        callback: Function to invoke after the workbench transition settles.
    """
    for module_name in ("PySide.QtCore", "PySide2.QtCore"):
        try:
            qt_core = importlib.import_module(module_name)
        except ImportError:
            continue
        qt_core.QTimer.singleShot(0, callback)
        return
    callback()


class ClothWorkbenchBase(Gui.Workbench if Gui is not None else object):
    """Small common registration shell for all Cloth workbenches."""

    def __init__(
        self,
        *,
        gui: object | None = None,
        toolbar_sink: Callable[..., object] | None = None,
        menu_sink: Callable[..., object] | None = None,
    ) -> None:
        """Initialize command registration and optional injectable GUI sinks.

        Args:
            gui: GUI API object to use, defaulting to FreeCAD's imported GUI module.
            toolbar_sink: Optional replacement for FreeCAD's toolbar registration method.
            menu_sink: Optional replacement for FreeCAD's menu registration method.
        """
        if Gui is not None:
            super().__init__()
        self._gui = cast("_WorkbenchGui | None", Gui if gui is None else gui)
        self._toolbar_sink = toolbar_sink
        self._menu_sink = menu_sink
        self.commands: list[str] = []

    @staticmethod
    def normalize_commands(commands: Iterable[object]) -> list[str]:
        """Return non-empty command names in first-seen order without duplicates.

        Args:
            commands: Arbitrary command identifiers to normalize.

        Returns:
            Unique, non-empty string command names in their original order.
        """
        return list(dict.fromkeys(str(command) for command in commands if str(command)))

    # Compatibility alias for historical callers; new code should use the public name.
    @staticmethod
    def _normalize_commands(commands: Iterable[object]) -> list[str]:
        """Normalize command identifiers using the established public helper.

        Args:
            commands: Arbitrary command identifiers to normalize.

        Returns:
            Unique, non-empty string command names in their original order.
        """
        return ClothWorkbenchBase.normalize_commands(commands)

    def _register_groups(
        self,
        groups: Iterable[tuple[str | None, Iterable[object]]],
        toolbar_name: str | None = None,
        toolbar_commands: Iterable[object] | None = None,
    ) -> None:
        """Register toolbar and menu groups while rejecting duplicate commands.

        Args:
            groups: Ordered pairs of group labels and command identifiers.
            toolbar_name: Optional name for a single toolbar containing all commands.
            toolbar_commands: Optional command subset to use when a named toolbar is set.

        Raises:
            ValueError: If a command is assigned to more than one group.
        """
        if self.commands:
            return
        normalized: list[tuple[str, list[str]]] = []
        seen: list[str] = []
        for group_name, commands in groups:
            group_commands = self.normalize_commands(commands)
            duplicates = [command for command in group_commands if command in seen]
            if duplicates:
                msg = f"commands registered in multiple groups: {', '.join(duplicates)}"
                raise ValueError(msg)
            if group_name and group_commands:
                normalized.append((str(group_name), group_commands))
                seen.extend(group_commands)
        self.commands = [command for _, commands in normalized for command in commands]
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

    def register(
        self,
        groups: Iterable[tuple[str | None, Iterable[object]]],
        toolbar_name: str | None = None,
        toolbar_commands: Iterable[object] | None = None,
    ) -> None:
        """Register menu and toolbar commands for this workbench.

        Args:
            groups: Ordered pairs of group labels and command identifiers.
            toolbar_name: Optional name for a single toolbar containing all commands.
            toolbar_commands: Optional command subset to use when a named toolbar is set.
        """
        self._register_groups(groups, toolbar_name=toolbar_name, toolbar_commands=toolbar_commands)

    def get_resources(self) -> dict[str, str]:
        """Return the menu label, tooltip and icon fields consumed by FreeCAD.

        Returns:
            Mapping with FreeCAD's MenuText, ToolTip and Icon resource keys.
        """
        return {"MenuText": self.MenuText, "ToolTip": self.ToolTip, "Icon": self.Icon}

    @staticmethod
    def activated() -> None:
        """Provide the no-op activation hook expected by FreeCAD workbenches."""

    def deactivated(self) -> None:
        """Run registered transient cleanup after switching away from Cloth."""
        callback = _WORKBENCH_DEACTIVATION_STATE.callback
        if callback is None:
            return

        def finish_deactivation() -> None:
            """Leave Cloth-owned transient UI active when switching between Cloth tools."""
            active_name = ""
            if self._gui is not None:
                with suppress(AttributeError, RuntimeError, TypeError):
                    active_workbench = cast(
                        "Callable[[], _ActiveWorkbench]",
                        getattr(self._gui, "activeWorkbench"),
                    )
                    active_name = str(active_workbench().name()).lower()
            # FreeCAD may deliver Activated() for the new workbench before this hook.
            if active_name.startswith("cloth"):
                return
            with suppress(AttributeError, RuntimeError, TypeError, ValueError):
                callback()

        _defer_workbench_transition(finish_deactivation)

    def context_menu(self, recipient: str) -> None:
        """Add this workbench's commands to the supported view or tree context menu.

        Args:
            recipient: FreeCAD context-menu target, such as view or tree.
        """
        if self._gui is not None and recipient in {"view", "tree"} and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    @staticmethod
    def get_class_name() -> str:
        """Return the FreeCAD workbench class identifier.

        Returns:
            Fully qualified GUI workbench class name expected by FreeCAD.
        """
        return "Gui::PythonWorkbench"


# FreeCAD calls these mixed-case names as part of its public workbench protocol.
# Keep the Python implementations lint-friendly while retaining the host API.
for _callback_name, _implementation in (
    ("GetResources", ClothWorkbenchBase.get_resources),
    ("Activated", staticmethod(ClothWorkbenchBase.activated)),
    ("Deactivated", ClothWorkbenchBase.deactivated),
    ("ContextMenu", ClothWorkbenchBase.context_menu),
    ("GetClassName", staticmethod(ClothWorkbenchBase.get_class_name)),
):
    setattr(ClothWorkbenchBase, _callback_name, _implementation)

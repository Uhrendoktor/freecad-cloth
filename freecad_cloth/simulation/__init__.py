"""Cloth Simulation workbench package."""

from .workbench import ClothSimulationWorkbench

try:
    import FreeCADGui as Gui
except ImportError:  # pragma: no cover
    Gui = None

if Gui is not None and hasattr(Gui, "listCommands"):
    from . import RealtimePreview  # noqa: F401,E402

__all__ = ["ClothSimulationWorkbench"]

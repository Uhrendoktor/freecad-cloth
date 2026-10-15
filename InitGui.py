"""Classic FreeCAD GUI entry point for direct installation in a Mod directory."""

from pathlib import Path

from freecad_cloth.bootstrap import initialize_workbenches

initialize_workbenches(Path(__file__).resolve().parent)

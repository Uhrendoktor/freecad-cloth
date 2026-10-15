"""FreeCAD 1.1 namespaced GUI entry point for FreeCAD Cloth."""

from pathlib import Path

from freecad_cloth.gui import initialize_workbenches

ROOT = Path(__file__).resolve().parents[2]
initialize_workbenches(ROOT)

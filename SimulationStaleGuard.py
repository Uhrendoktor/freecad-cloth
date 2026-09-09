"""Compatibility shim for legacy FreeCAD workbench imports."""

import sys

from freecad_cloth.simulation import SimulationStaleGuard as _implementation

sys.modules[__name__] = _implementation

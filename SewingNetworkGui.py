"""Compatibility shim for legacy FreeCAD workbench imports."""

import sys

from freecad_cloth.sewing import SewingNetworkGui as _implementation

sys.modules[__name__] = _implementation

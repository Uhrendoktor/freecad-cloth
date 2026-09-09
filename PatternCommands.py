"""Compatibility shim for legacy FreeCAD workbench imports."""

from freecad_cloth.pattern.PatternCommands import *
from freecad_cloth.pattern.PatternCommands import __all__ as _PATTERN_COMMANDS_ALL

__all__ = _PATTERN_COMMANDS_ALL

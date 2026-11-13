# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compatibility alias for the historical lowercase avatar commands module path."""

from importlib import import_module
import sys

_canonical_module = import_module(".AvatarCommands", package=__package__)
sys.modules[__name__] = _canonical_module

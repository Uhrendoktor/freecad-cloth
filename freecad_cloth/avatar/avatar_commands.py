# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compatibility alias for the historical lowercase avatar commands module path."""

import sys
from importlib import import_module

_canonical_module = import_module(".AvatarCommands", package=__package__)
sys.modules[__name__] = _canonical_module

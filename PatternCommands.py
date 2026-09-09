"""Compatibility shim for legacy FreeCAD workbench imports.

Expose the package module itself so callers that monkeypatch or otherwise
introspect command handlers see the same module state as the canonical path.
"""

import sys

from freecad_cloth.pattern import PatternCommands as _implementation

sys.modules[__name__] = _implementation

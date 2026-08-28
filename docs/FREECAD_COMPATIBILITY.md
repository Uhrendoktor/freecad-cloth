# FreeCAD compatibility and workbench packaging

The current repository keeps the classic external-workbench entry points (`Init.py`/`InitGui.py`) to avoid disrupting existing installations. A namespaced/pip-style migration should be treated as a compatibility project rather than mixed into the core model.

Compatibility policy: core Python modules must run without FreeCAD; GUI code is isolated behind the workbench entry point; CI performs syntax/core tests independently and attempts a `freecadcmd` smoke test when the runtime is installed.

Migration plan: first add namespaced modules alongside the classic entry points, verify Addon Manager/package.xml behavior across supported FreeCAD releases, then switch the loader only after a release matrix passes. Until that work is completed, the classic layout is the safer supported structure.

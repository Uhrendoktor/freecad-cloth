# 2D drafting interaction prototype

The intended interaction model follows FreeCAD's existing sketch/property conventions without making GUI classes part of the core model. A Pattern object owns stable segment IDs; selection resolves to those IDs, while the task panel edits numeric parameters and constraints.

Visual layers: sewing boundary, cut boundary, construction geometry, and notches use separate display objects. Edge selection is by stable ID; seam pairing selects two edge IDs and then exposes normalized ranges/orientation. Undo/redo should be delegated to FreeCAD document transactions so geometry and semantic metadata change atomically.

Recommended abstraction boundary: `PatternGeometry`/`PatternModel` remain importable without FreeCAD; `InitGui.py` and future commands translate FreeCAD selections into model operations. GUI APIs should be version-gated and tested through import/registration smoke tests.

Prototype scope is deliberately small: create a parametric rectangle, edit width/height, select an edge, and expose its stable ID. Full task-panel implementation can follow once the model stabilizes.

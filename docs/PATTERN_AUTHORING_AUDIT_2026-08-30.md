# Pattern Workbench authoring audit — 2026-08-30

## Scope

Audited `PatternGui.py`, `PatternCommands.py`, `PatternModel.py`, `PatternGeometry.py`, `PatternSchema.py`, `PatternObjects.py`, `PatternSketch.py`, `SketchAuthority.py`, `PatternIR.py`, `PatternMarks.py`, and the existing pattern/FreeCAD GUI tests against a minimum professional 2D garment-pattern workflow.

## Findings

| Capability | Current state | Production assessment |
|---|---|---|
| Line segments | Native Sketcher lines are generated and constrained coincident | Good foundation |
| Curves / Bezier | PatternIR preserves native curve classes, but the creation adapter currently seeds only lines | Blocker for curved authoring |
| Parametric dimensions | Native Sketcher constraints are available; smoke coverage proves a dimensional constraint can drive the piece | High-value path; reuse Sketcher |
| Seam allowance | Persisted on PatternPiece and derived with Part/OCCT-compatible geometry | Usable, but offset self-intersection handling remains later work |
| Notches / grainline / internal marks | Persisted semantic mark objects and commands exist | Present; richer placement UX can follow |
| Grain / orientation | Grainline angle and FreeCAD Placement persist | Present |
| Validation | Prior validation was mostly implicit in recompute/IR consumers | **Gap:** explicit production validation command/task panel and persistent diagnostic state |
| Measurements | Geometry/IR can calculate edge lengths; no dedicated authoring measurement surface | Later UX improvement |
| Piece metadata | Name, stable PieceId, allowance, grainline and metadata model exist | Present |
| Symmetry / mirroring / duplication | No focused garment-authoring command | Later, after authoritative editing is stable |
| Undo / redo | FreeCAD document transactions/native Sketcher provide the right substrate, but custom drafting mutates directly | Native Sketcher should be the primary authoring surface |
| Expressions | FreeCAD/Sketcher supports them natively; no garment-specific wrapper needed yet | Reuse native facilities |
| Persistence | FreeCAD document properties plus Sketcher object are persistent; schema JSON is versioned separately | Good foundation |
| Sewing hand-off | Semantic edge IDs and PatternIR feed the Sewing workbench | Depends on stable Sketcher authority |

## Highest-value production feature selected

**Make native Sketcher authoring the explicit production path, with a first-class Edit Sketch command and explicit closed-boundary validation.**

This is deliberately smaller than implementing the entire CLO feature set. It removes the highest-risk workflow ambiguity: users need one authoritative, editable geometry source before seam allowance, marks, sewing, measurements and simulation can be trusted downstream.

### Design decision

1. `PatternPiece` remains the semantic FreeCAD document object.
2. When `GeometryAuthority == "Sketcher"`, the linked `Sketcher::SketchObject` is the geometric source of truth.
3. `PatternIR.from_sketches()` is the adapter into solver-neutral geometry and retains native curve kind/semantic IDs.
4. Derived sampled outlines, seam allowances and meshes are compatibility/derived data only.
5. `ClothPattern_EditSketch` enters FreeCAD's native Sketcher editor instead of duplicating a constraint solver in a custom canvas.
6. `ClothPattern_ValidatePiece` runs a read-only topology conversion check and persists `ValidationStatus`/`ValidationMessage` on the PatternPiece, with a task panel for repair feedback.
7. Validation is non-authoritative: it never repairs or replaces authored geometry.

## Why not implement the whole feature matrix now?

Curved edge creation, advanced offset cleanup, mirror/duplicate, measurement tooling and richer garment marks are valuable, but they all depend on a stable authoring authority. Implementing them before that contract is hardened would multiply competing geometry paths and make downstream invalidation harder to reason about.

The next parity increment should therefore extend the native Sketcher adapter to seed/edit arcs, Beziers/BSplines and their semantic edge IDs, followed by dedicated garment transformations.

## Verification added in this increment

- Headless validation tests for closed and open Sketcher-style boundaries.
- GUI command-contract coverage for Edit Sketch and Validate Piece.
- Real FreeCAD smoke coverage for native Sketcher authority, dimensional edit propagation, and persisted validation measurements.
- Validation state is stored on the FreeCAD PatternPiece, so it survives document save/reload like the other semantic properties.

## Remaining known gap

The native Sketcher creation helper currently creates a line-only initial boundary. A user can continue editing the native sketch with Sketcher's own curve tools, but the workbench does not yet provide dedicated garment-oriented curve creation commands. That is intentionally deferred to the next focused parity task rather than introducing a second custom geometry editor now.

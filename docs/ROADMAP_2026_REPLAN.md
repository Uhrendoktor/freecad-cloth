# Cloth Workbench 2026 Replan

## Supervisor decision

The previous roadmap is no longer sufficient as a release plan. It correctly established native Sketcher, semantic sewing, deterministic simulation, and FreeCAD/Xvfb acceptance, but it under-specified the user-facing garment workflow and treated several CLO behaviors as isolated features.

The revised release target is an end-to-end FreeCAD-native garment system with three cooperating workbenches:

`Cloth Pattern -> Cloth Sewing -> Cloth Simulation`

The document model is authoritative; simulation meshes are disposable derived state.

## Research conclusions

CLO separates 2D pattern authoring from 3D fitting. Important behaviors are not just drawing tools: seam allowances are editable semantic edge data, notches are manufacturing references, sewing has direction and free/M:N forms, arrangement points provide repeatable initial 3D placement, avatars expose anthropometric measurements and poses, and particle distance explicitly trades simulation quality for speed. CLO also keeps fabric/material properties and simulation controls visible in a property-oriented workflow.

FreeCAD already provides the strongest pieces of the architecture: `Sketcher::SketchObject` for parametric 2D geometry and constraints; document objects, Links, Placements, expressions and recompute/save semantics for persistence; Part/OCCT for curves and derived outlines; Mesh/MeshPart for solver meshes; and TechDraw/Draft for production drawing/export. The project must not create a second dimensional sketch/constraint kernel.

## Revised workbench contracts

### 1. Cloth Pattern — authoritative 2D construction

**Purpose:** create and edit production pattern pieces.

Required commands:
- New Pattern Piece
- Edit Pattern / open native Sketcher
- Line, arc, B-spline and construction geometry through Sketcher
- Coincident, tangent, horizontal/vertical, symmetry and dimensional constraints through Sketcher
- Mirror / transform helpers
- Seam Allowance
- Notch
- Grainline
- Internal Mark / fold / dart metadata
- Validate Pattern
- Create Simulation Mesh
- Show/Hide construction metadata

Persistent object model:
- PatternPiece -> authoritative `Sketcher::SketchObject`
- PatternMark -> semantic mark linked to stable sketch geometry
- derived seam allowance / inspection geometry
- measurement/expression links for parametric drafting

Acceptance: a curved multi-piece garment can be edited with native Sketcher constraints and all semantic references remain safe across recompute/save/reload.

### 2. Cloth Sewing — semantic assembly

**Purpose:** turn pattern boundaries into an explicit sewing graph.

Required commands:
- Create Seam
- Segment/Free Sewing
- M:N Sewing
- Reverse Direction
- Alignment / correspondence mode
- Edit seam ranges
- Validate Sewing
- Repair Sewing
- Show 2D
- Create Fitting Scene
- Add/Remove Pattern Pieces
- Set Arrangement

The new curved-correspondence API merged in PR #238 is the validation foundation. The next layer must integrate it into the task panel and persistent Seam objects without duplicating seam state.

Acceptance: users can create 1:1 and M:N seams, see length/reversal/range diagnostics, repair them, and save/reload the sewing graph.

### 3. Cloth Simulation — 3D fitting and physics

**Purpose:** arrange, mesh, drape and inspect the sewn garment.

Required commands:
- Create/Select Drape Target
- Create/Configure Mannequin
- Arrangement Points / placement gizmo
- Generate Preview Mesh
- Generate Final Mesh
- Simulate / Pause / Step / Reset
- Pin / Unpin
- Material/Fabric preset
- Particle Distance / quality preset
- Collision thickness/skin offset
- Solver iterations/substeps
- Fit diagnostics
- Show simulation status and invalidation reason

The solver consumes a solver-neutral collision surface and pattern/sewing intermediate representation. It must not inspect Sketcher internals or require a mannequin-specific code path.

## Cross-workbench interaction

```text
Sketcher geometry
      |
      v
PatternPiece + PatternMarks
      |
      v
PatternIR -----> SewingGraph
      |               |
      +---------------+
              |
              v
        SimulationScene
        /             \
 PatternMesh       DrapeTarget
                     /   \
              Mannequin   FreeCAD Shape/Mesh
```

A pattern edit invalidates sewing/mesh/simulation state through document dependencies and semantic signatures. A seam edit invalidates the simulation scene. A target move/edit invalidates collision data. Rebuilding is deterministic and explicit.

## UI strategy

Do not clone the entire CLO UI. Use FreeCAD's workbench selector, toolbars, menus, Tree view and Property Editor. Use task panels only for multi-step operations.

### Pattern toolbar
`New Piece | Edit Sketch | Constraint/Measure | Seam Allowance | Notch | Grainline | Mark | Validate | Mesh`

### Sewing toolbar
`Create Seam | Free Sewing | M:N | Reverse | Alignment | Validate | Repair | Show 2D | Fitting Scene`

### Simulation toolbar
`Target | Mannequin | Arrange | Preview Mesh | Final Mesh | Simulate | Step | Reset | Pin | Fabric | Quality | Diagnostics`

Context-sensitive activation should prevent invalid operations before execution.

## Release gates

### P0-A — Architecture and persistence
- Native Sketcher authority
- stable semantic references
- PatternIR
- SewingGraph persistence
- deterministic invalidation

### P0-B — Sewing UX
- 1:1, 1:N and M:N
- curved correspondence integrated into GUI
- reversal/alignment/length diagnostics
- repair states

### P0-C — Human fitting
- parametric mannequin with authoritative measurements
- stable landmarks and arrangement points
- persistent collision representation
- mannequin -> DrapeTarget provider

### P0-D — General draping target
- arbitrary Part/PartDesign/Mesh target
- placement-aware collision invalidation
- collision quality presets
- future multi-target-ready model

### P0-E — Simulation production workflow
- material presets
- preview/final quality
- simulation status/invalidation
- pinning and diagnostics
- deterministic save/reload

### P1 — Pattern production parity
- richer seam allowance corner types
- notch variants and placement tools
- grainline/fold/dart/pleat semantics
- grading/size groups
- measurement-driven drafting helpers
- TechDraw/DXF/SVG production export

### P2 — Optional performance backends
Benchmark Tissu/PositionBasedDynamics/other native backends only after the reference CPU path and all P0/P1 gates are release-stable.

## Definition of a fully working workbench

The project is not complete when individual scripts exist. It is complete when a fresh FreeCAD session can:

1. create a garment document;
2. create/edit at least two native Sketcher-backed pattern pieces;
3. add seam allowance, notches and grainline/internal marks;
4. create curved 1:1 and M:N sewing relationships;
5. validate/repair seam correspondence;
6. create/configure a mannequin or select arbitrary FreeCAD geometry as a target;
7. arrange pieces in 3D;
8. generate a preview mesh and simulate;
9. change a pattern measurement and observe deterministic downstream invalidation;
10. recompute/rebuild and simulate again;
11. save, close, reload and continue editing;
12. export production 2D output without losing semantic model state.

Every P0 step requires headless regression coverage plus real FreeCAD/Xvfb acceptance.

## Research references

- CLO Help Center: Simulation, 2D Pattern Information, seam allowance, notches, free/segment sewing, arrangement points, avatar editor, particle distance and grading.
- FreeCAD documentation: Sketcher SketchObject, Sketcher scripting, DocumentObject, TechDraw DXF/SVG export.
- Existing project research: `docs/SEWING_WORKFLOW_RESEARCH.md`.

# Cloth Workbench 2026 Replan

## Supervisor decision

The previous roadmap established the correct architectural direction, but it was too feature-oriented. The release plan is now organized around a user-visible garment loop and explicit workbench contracts:

`Cloth Pattern -> Cloth Sewing -> Cloth Simulation`

The document model is authoritative; solver meshes and collision caches are disposable derived state.

## Research conclusions

Current CLO documentation confirms that the important behaviors are not merely drawing primitives: sewing has segment/free and M:N forms; direction and sewing-line correspondence matter; particle distance is an explicit quality/performance control; arrangement points provide semantic 3D starting placement; avatar sizing is part of fitting; and grading includes persistent per-size distances, offsets, grade points and notch rules. See `docs/RESEARCH_2026_CLO_FREECAD.md` for the source list and FreeCAD capability mapping.

FreeCAD already supplies the strongest architecture primitives: native `Sketcher::SketchObject` geometry/constraints, expressions, document Links/Groups/Placement/recompute/save semantics, Part/OpenCascade geometry, Mesh/MeshPart, and TechDraw DXF/SVG export. The project must not introduce a second general-purpose sketch or constraint kernel.

## Workbench contracts

### 1. Cloth Pattern — authoritative 2D construction

**Purpose:** create and edit production pattern pieces while keeping native Sketcher authoritative.

Required user actions:
- New Pattern Piece
- Edit Sketch / open native Sketcher
- line, arc, B-spline and construction geometry through Sketcher
- dimensional/geometric constraints through Sketcher
- mirror/transform helpers
- Seam Allowance
- Notch
- Grainline
- Internal Mark / fold / dart metadata
- Validate Pattern
- Generate Preview/Simulation Mesh
- Show/Hide construction metadata

Persistent model:
- PatternPiece -> authoritative `Sketcher::SketchObject`
- semantic PatternMark objects
- derived seam-allowance/inspection geometry
- measurement/expression links
- stable semantic edge identities independent of raw `EdgeN` ordering

### 2. Cloth Sewing — semantic assembly

**Purpose:** turn pattern boundaries/internal lines into a persistent sewing graph.

Required user actions:
- Segment Sewing
- Free Sewing
- 1:N and M:N Sewing
- Reverse Direction
- correspondence/alignment mode
- edit seam ranges
- Validate Sewing
- Repair Sewing
- Show 2D
- Create Fitting Scene
- Add/Remove Pattern Pieces
- Set Arrangement

The curved-correspondence validator is the foundation; the next implementation must make it actionable in the native task panel and preserve one authoritative seam state.

### 3. Cloth Simulation — 3D fitting and physics

**Purpose:** arrange, mesh, drape and inspect the sewn garment.

Required user actions:
- Create/Select Drape Target
- Create/Configure Mannequin
- Arrangement Points / placement
- Preview Mesh / Final Mesh
- Run / Step / Reset / Pause where supported
- Pin / Unpin
- Fabric preset/material properties
- Particle Distance / quality preset
- collision thickness / skin offset
- solver iterations/substeps
- diagnostics and invalidation status

The solver consumes PatternIR/SewingGraph and a target-neutral collision surface. It must not inspect Sketcher internals or require a mannequin-specific path.

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

Invalidation rules are explicit:
- Sketch/PatternPiece geometry change -> invalidate affected seam resolution, mesh and simulation.
- Seam/SewingGraph change -> invalidate simulation assembly/mesh as required.
- DrapeTarget geometry/Placement/tessellation change -> invalidate collision cache and simulation.
- Quality/material change -> rebuild only the derived mesh/solver state that depends on it.

## UI strategy

Use FreeCAD's workbench selector, native menus/toolbars, Tree view, Property Editor and task panels. Do not clone the CLO UI wholesale. Task panels are reserved for multi-step selection/edit operations.

### Pattern toolbar
`New Piece | Edit Sketch | Measure/Constraint | Seam Allowance | Notch | Grainline | Mark | Validate | Mesh`

### Sewing toolbar
`Segment | Free | M:N | Reverse | Alignment | Validate | Repair | Show 2D | Fitting Scene`

### Simulation toolbar
`Target | Mannequin | Arrange | Preview Mesh | Final Mesh | Run | Step | Reset | Pin | Fabric | Quality | Diagnostics`

Common UI rules:
- icons represent actions; values/options remain native text controls;
- primary/secondary/destructive actions have consistent hierarchy;
- command activation prevents invalid operations;
- task panels expose persistent properties rather than transient hidden state;
- every major action has a tooltip explaining effect and units.

## Reworked milestones

### M0 — CI and repository control plane
- one canonical workflow
- terminal-green verification for every merged implementation
- AGENT_STATUS kept current
- stale branches/PRs audited before new work
- canonical GUI screenshots capture the full FreeCAD window

### M1 — End-to-end garment fixture (P0 release gate)
- two or more native Sketcher PatternPieces
- at least one curved seam
- persistent 1:1 and M:N sewing
- arrangement/fitting scene
- drape target
- simulation
- save/reload
- upstream pattern edit -> deterministic invalidation -> rebuild -> simulation

### M2 — Sewing UX completion
- curved correspondence integrated into task panel
- reverse/alignment/range controls
- actionable repair states
- transactional M:N editing
- 2D/3D seam visualization

### M3 — Simulation production workflow
- DrapeTarget authoritative in Simulation
- mannequin + arbitrary FreeCAD Shape/Mesh targets
- arrangement points
- preview/final quality presets
- explicit lifecycle/status
- pinning and diagnostics

### M4 — Pattern production minimum
- seam allowance
- notches
- grainline
- internal marks/fold/dart metadata
- validation and derived inspection geometry

### M5 — Manufacturing parity
- grading/size groups
- measurement-driven helpers
- richer seam allowance corner behavior
- TechDraw/DXF/SVG production export and round-trip tests

### M6 — Optional performance/advanced features
- benchmark optional native solvers only after P0/P1 are green
- advanced avatar/pose features
- multiple collision targets
- modular/auto-sewing workflows

## Current status and immediate sequence

The mainline already contains the architectural baseline for native Sketcher authority, semantic sewing, the parametric mannequin and the general DrapeTarget. The remaining release blockers are integration/UX rather than another foundational rewrite.

Immediate supervisor sequence:
1. Complete the CI control-plane repair and keep only the canonical workflow.
2. Finish the curved correspondence task-panel integration.
3. Make DrapeTarget authoritative throughout Simulation and expose target-aware invalidation/status.
4. Replace legacy drafting as the default Pattern entry point with native Sketcher while retaining migration support.
5. Add PatternMarks (seam allowance/notch/grainline/internal marks) as persistent semantic objects.
6. Finish the canonical create -> sew -> arrange -> drape -> edit -> invalidate -> rebuild -> save/reload fixture.
7. Finish production export/install acceptance.
8. Benchmark optional solver backends last.

## Release gates

### P0-A — Architecture and persistence
- native Sketcher authority
- stable semantic references
- PatternIR
- SewingGraph persistence
- deterministic invalidation

### P0-B — Sewing UX
- 1:1, 1:N and M:N
- curved correspondence in GUI
- reversal/alignment/length diagnostics
- repair states

### P0-C — Human fitting
- authoritative anthropometric mannequin
- landmarks and arrangement points
- persistent collision representation
- mannequin -> DrapeTarget provider

### P0-D — General draping
- arbitrary Part/PartDesign/Mesh target
- placement-aware collision invalidation
- quality controls
- target-neutral solver interface

### P0-E — Simulation production workflow
- material presets
- preview/final quality
- lifecycle/status/invalidation
- pinning/diagnostics
- deterministic save/reload

### P1 — Pattern/manufacturing parity
- marks and seam allowance
- grading/size groups
- measurement helpers
- TechDraw/DXF/SVG export

### P2 — Optional performance
No optional native solver backend becomes a release dependency before the reference CPU path and all P0/P1 gates are stable.

## Definition of a fully working workbench

The project is complete only when a fresh FreeCAD session can:

1. create a garment document;
2. create/edit at least two native Sketcher-backed pattern pieces;
3. create seam allowance, notches and grainline/internal marks;
4. create curved 1:1 and M:N sewing relationships;
5. validate and repair seam correspondence;
6. create/configure a mannequin or select arbitrary FreeCAD geometry as a target;
7. arrange pieces in 3D;
8. generate a preview mesh and simulate;
9. change an upstream pattern measurement and observe deterministic downstream invalidation;
10. rebuild and simulate again;
11. save, close, reload and continue editing;
12. export production 2D output without losing semantic model state.

Every P0 step requires headless regression coverage plus real FreeCAD/Xvfb acceptance. Utility scripts alone never satisfy a release gate.

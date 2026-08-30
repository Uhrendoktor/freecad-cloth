# FreeCAD Cloth Workbench — 2026 Supervisor Roadmap

## Purpose

The release target is three real FreeCAD workbenches that form one persistent document workflow:

`Pattern (native Sketcher) -> Sewing (semantic seams) -> Simulation (arrangement + target + drape)`

Utility scripts are test/support infrastructure only; they are never the product acceptance surface.

## Research baseline

CLO 2026 exposes pattern metadata (fabric, grainline, shrinkage, mirror/cut information and revision/stage data), a Property Editor spanning patterns, sewing, fabric, avatar and simulation, persistent 3D arrangement properties, smart arrangement, CPU/GPU simulation modes, and explicit simulation quality modes. Its sewing surface includes Segment, Free, 1:N and M:N variants plus Reverse/Unlink and directional-notch behavior. These behaviors are useful parity references, not requirements to copy proprietary implementation.

FreeCAD already provides the core primitives we should reuse: Sketcher geometry and constraint solving, named expressions, document properties/Links/Groups and dependency/recompute, Part/OpenCascade geometry, Mesh, and Python workbench registration.

## Replanned release gates

### P0-A — CI and public-workbench release gate

- Canonical Actions workflow schedules every required job deterministically.
- Real FreeCAD/Xvfb is mandatory; no skipped GUI jobs or utility-only substitutes.
- GUI fixture must prove Pattern, Sewing and Simulation task panels/toolbars and retain diagnostics/screenshots on failure.
- Current blocker: #347, simulation fixture creates/arranges panels that are not sufficiently tessellated for the release assertion.

### P0-B — DrapeTarget authority

- Persistent target-neutral collision object.
- Mannequin and arbitrary FreeCAD Shape/Mesh are providers.
- Explicit `READY/STALE/INVALID/REFRESHING` lifecycle.
- Ordinary recompute never consumes stale collision geometry or crashes.
- Step/Run are blocked until Refresh; Reset remains available.
- Save/reload preserves target authority and invalidation reason.

### P0-C — Canonical garment workflow

One public-workbench scenario must perform:

1. create two or more native Sketcher PatternPieces;
2. edit dimensions/expressions and retain semantic geometry IDs;
3. create curved, reversed and M:N/free sewing relationships;
4. persist 3D arrangement state;
5. select/configure a mannequin or arbitrary DrapeTarget;
6. build simulation meshes using a quality/particle-distance setting;
7. drape deterministically on the CPU reference backend;
8. save, close, reload;
9. change an upstream pattern/target property and observe deterministic downstream invalidation;
10. Refresh/rebuild and simulate again.

### P0-D — Simulation quality and physical controls

Required persisted controls:

- particle distance / mesh quality;
- fabric density and thickness;
- stretch, shear and bend response;
- friction;
- solver substeps/iterations;
- collision deflection/thickness/skin offset;
- visible state and actionable failure reasons.

Quality changes must change derived mesh/solver state rather than merely changing labels.

### P0-E — UX and persistence

Pattern, Sewing and Simulation must use a consistent action hierarchy:

- primary actions are obvious;
- recovery/repair is secondary and explicit;
- Reset is visually separate from normal operations;
- units are visible on physical quantities;
- properties remain inspectable in the FreeCAD Property Editor;
- undo/recompute/save/reload behave as native FreeCAD operations.

### P1 — Pattern authoring and production semantics

- Native Sketcher remains authoritative for geometry and constraints.
- Cloth adds semantic PatternPiece metadata, grainline, seam allowance, notches, darts/folds, marks and stable edge identity.
- Explicit topology repair is required after destructive Sketch edits; never ordinal-retarget seams silently.
- Curves and manufacturability validation must be first-class.
- Export/TechDraw/print-layout capabilities follow the core authoring contract.

### P2 — Optional parity

Defer until P0/P1 are green: UV/texture production tools, animation editor, trims/buttons/zipper asset systems, full sculpting, industrial nesting/marker management, fabric-kit hardware, GPU-specific optimization and optional native solver backends.

## UI command matrix

### Cloth Pattern

**Creation:** Create Pattern Piece, Create Piece with Sketch, Create Sketcher Geometry, Open Pattern Drafting.

**Editing:** Edit Pattern Piece, Show Pattern 2D, repair topology.

**Marks:** seam allowance, grainline, notches and future internal construction marks.

Pattern should deliberately reuse Sketcher's native edit task panel for geometry/constraints rather than creating a competing sketch editor.

### Cloth Sewing

**Creation:** Segment/edge seam, Free Sewing, M:N sewing, Sewing Network.

**Editing:** Reverse, alignment/correspondence, range, stitch sampling, transactional network edits.

**Validation:** length mismatch, direction/reversal, invalid semantic references, repair correspondence, Show 2D.

The persistent object is the seam/network; the task panel is only its editing frontend.

### Cloth Simulation

**Scene:** select cloth pieces, arrangement, DrapeTarget, fabric/material.

**Quality:** particle distance/preset, solver iterations/substeps, collision deflection/thickness/skin offset.

**Execution:** Step, Run N, Reset, Refresh DrapeTarget.

**Diagnostics:** target lifecycle, mesh counts, particle count, finite-state, simulation time and actionable invalidation reason.

## Dependency graph contract

```text
Sketcher::SketchObject
        |
        v
   PatternPiece
        |
        +----> Seam / SewingNetwork
        |          |
        v          v
     PatternIR -> simulation mesh
                    |
       DrapeTarget -+-> CPU solver -> derived Mesh::Feature
```

Sketcher owns geometry. Cloth owns garment semantics and lifecycle. The solver consumes a resolved intermediate representation and collision surface, not raw Sketcher internals.

## Supervisor operating rules

- Audit every open issue and PR before accepting a slice.
- Prefer one narrow PR per architectural change.
- Re-cut stale branches from current main rather than merging old heads.
- Keep one canonical GitHub Actions workflow.
- Never weaken a failing GUI assertion to make CI green; fix the fixture or product behavior.
- Update `AGENT_STATUS.md` at every slice start/handoff.
- A gate is complete only after canonical CI is green and merged-main verification is green.

# Cloth Workbenches — Scope Plan

## Goal
FreeCAD-native garment workflow: `Pattern → Sewing → Arrange/Fit → Simulate → Output`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; the solver owns physics. Derived mesh/collision/simulation state is rebuildable.

## Prototype
Prove the boundaries with a small garment:
- Native Sketcher-backed PatternPiece.
- Persistent semantic seams/marks.
- Segment/free sewing; direction/reversal; staged commit/cancel.
- Target-neutral DrapeTarget with human mannequin and generic FreeCAD geometry providers.
- Deterministic arrangement/reset, preview mesh, CPU reference simulation.
- Save/reload and explicit invalidation.

**Exit:** 2–4 pieces can be created, sewn, arranged on either target, simulated, saved/reloaded, edited, invalidated, rebuilt and simulated again.

## MVP
Make the workflow repeatable:
- Stable semantic edge references and topology repair.
- 1:N/M:N/free sewing with length-aware correspondence and repair UX.
- Arrangement points, wrap/superimpose/reset.
- Parametric human measurements and basic poses.
- Generic CAD drape targets.
- Particle-distance and fabric presets; pinning; deterministic Run/Step/Reset.
- Pattern production basics: seam allowance, notches, grading, 2D export.

**Exit:** a user can make a modest garment, fit it to a human or CAD target, control simulation quality/materials, recover from invalid state, save/reload safely and export usable 2D data.

## Production
Only after the end-to-end contracts are stable:
- Higher-fidelity replaceable human provider.
- Multiple collision targets and optional subelement targets.
- Stress/strain/fit/pressure diagnostics.
- Grading review, nesting, plotting and manufacturing validation.
- Pleats/folds, topstitch, buttons/buttonholes/tacks, linings/facings, modular blocks and POM.
- Optional solver backends.

## Implementation order
1. P0 stale-target safety + canonical end-to-end workflow.
2. Sewing M:N/free/repair UX.
3. Mannequin + arrangement acceptance.
4. Generic DrapeTarget acceptance.
5. Simulation quality/material controls.
6. Pattern production/export.
7. Production avatar fidelity.
8. Diagnostics/manufacturing.
9. Advanced construction.
10. Optional solver benchmarks.

## UI rules
Task panels use: **Context → Primary action → Secondary tools → Parameters → Recovery**.

Persistent links/settings belong in the document/Property Editor. Apply/Cancel stages edits. Stale state shows a reason and recovery action. Run is primary simulation action; Step is secondary; Reset is recovery. Sewing commits explicitly; Esc cancels and Delete undoes the latest staged selection.

## Avatar rule
The human mannequin and generic FreeCAD object are **providers of one DrapeTarget contract**, not separate solver paths. A high-fidelity provider comes later without changing Pattern/Sewing/Simulation APIs.

## Scope guard
Do not replace Sketcher, add a second scene graph/solver/persistence model, multiply CI workflows, or pull production features forward merely because CLO has them. Every new feature must identify its persistent authority, existing boundary, invalidation/recovery behavior, and public-workbench acceptance test.

## Agent handoff
Every implementation issue states: authority/API, allowed files, dependencies, tests, FreeCAD/Xvfb acceptance, artifacts, non-goals, and CI constraints.

# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The initial PR/issue backlog and all open implementation PRs were audited before new work. PR #217 (task-panel transaction) and the rebased replacement #239 (Sewing selection validation) were merged after terminal-green canonical CI. PR #238 (curved-seam correspondence validation) was then merged after terminal-green canonical CI. Stale avatar/status/drape PRs (#208, #216, #234, #237) were closed as superseded rather than carrying conflicting architecture forward.

The roadmap has been reworked around the actual end-to-end product: native Sketcher pattern authoring, semantic sewing, first-class human/general drape targets, and a production-oriented simulation workbench. See `docs/ROADMAP_2026_REPLAN.md`.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority for linked PatternPieces; PatternIR preserves curve kind and endpoint connectivity.
- **P0-B Sewing:** semantic seam references, Show 2D, M:N SewingNetwork, task-panel invalid-reference rejection, and the reusable curved correspondence validator are merged.
- **P0-C Simulation:** quality/material properties and deterministic particle-distance mesh generation are implemented; simulation lifecycle/status remains a follow-up integration task.
- **P0-D Acceptance:** canonical FreeCAD/Xvfb covers the registered Pattern/Sewing/Simulation workflow, native Sketcher authority, persisted seams/M:N network, quality-density change, save/reload, upstream edit invalidation and re-simulation.
- **P0-C Human fitting / P0-D Drape targets:** re-planned; implementation must establish a common target-neutral collision API before adding more mannequin-specific behavior.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | baseline done; release regression follow-up |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Sewing invalid-reference task acceptance | #226, merged | done |
| Curved seam correspondence validator | #238, merged | done; GUI integration next |
| Simulation quality/material density | #145/#229 | active P0 integration |
| Parametric avatar/mannequin | #203 | active P0 reimplementation |
| General DrapeTarget | #228 | active P0 reimplementation |
| Canonical GUI acceptance | #155/#143/#229 | active P0 follow-up |
| Pattern authoring parity | #162 | active P1 |

## Current acceptance status

1. Workbench registration/internal IDs: **passed**.
2. Native Sketcher authority and save/reload: **passed in canonical E2E**.
3. Persisted semantic seams and M:N SewingNetwork: **passed in canonical E2E**.
4. Curved seam correspondence validator: **merged and terminal-green; GUI integration pending**.
5. Particle-distance quality changes deterministic derived mesh density: **passed**.
6. Upstream edit invalidation and re-simulation: **passed in canonical E2E**.
7. Human mannequin as a first-class fitting target: **not yet release-complete**.
8. Arbitrary FreeCAD geometry as a first-class drape target: **not yet release-complete**.
9. Production export/package/install acceptance: **not yet release-complete**.

## Rules

1. Sketcher geometry is source geometry; PatternPiece is the semantic garment object.
2. PatternIR is solver-neutral and preserves native curve identity/connectivity.
3. Sewing references use semantic IDs/signatures, never fragile insertion-order edge numbers.
4. Simulation consumes derived geometry and invalidates/rebuilds deterministically after source edits.
5. Prefer native FreeCAD Sketcher/Part/Mesh/TechDraw/document dependencies over parallel CAD infrastructure.
6. Every P0 feature requires headless tests plus real FreeCAD smoke/Xvfb coverage.
7. Keep one canonical CI workflow; do not create push-triggered workflow variants.
8. A workbench feature is not complete when a utility module exists; the public FreeCAD command/task-panel/document workflow must work end-to-end.
9. The supervisor must keep `AGENT_STATUS.md` current at milestone handoff and audit stale branches before new implementation.

## Next supervisor sequence

1. Reimplement the parametric mannequin as a persistent FreeCAD document object with authoritative anthropometric properties, landmarks, pose and a collision-surface provider.
2. Generalize collision/drape target handling so mannequin and arbitrary Part/PartDesign/Mesh objects use the same solver-neutral interface.
3. Integrate curved correspondence into the Sewing task panel with actionable repair states, reverse/alignment controls and M:N editing.
4. Replace legacy drafting as the default Pattern UI with native Sketcher commands while retaining migration support.
5. Add explicit seam-allowance/notch/grainline/internal-mark derived features and production size/grading semantics.
6. Finish canonical create -> sew -> arrange -> drape -> edit -> invalidate -> rebuild -> save/reload acceptance.
7. Finish TechDraw/DXF/SVG round-trip and package/install validation.
8. Benchmark optional native solvers only after all P0/P1 gates are green.

# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

Initial PR/issue backlog was audited before new implementation. Stale stacked branches were closed; validated slices are merged only after terminal-green canonical CI. The first integrated P0-C/P0-D acceptance gate is now merged.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority for linked PatternPieces; PatternIR preserves curve kind and endpoint connectivity.
- **P0-B Sewing:** semantic seam references, Show 2D, M:N SewingNetwork, and task-panel invalid-reference rejection are merged.
- **P0-C Simulation:** quality/material properties, avatar collision source, and deterministic particle-distance mesh generation are implemented.
- **P0-D Acceptance:** canonical FreeCAD/Xvfb now covers registered Pattern/Sewing/Simulation workbenches, native Sketcher authority, persisted seams/M:N network, quality-density change, save/reload, upstream edit invalidation and re-simulation; the integrated gate is merged as #229.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | done |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Sewing invalid-reference task acceptance | #226, merged | done |
| Simulation quality/material density | #145/#229, merged gate | active P0 follow-up |
| Parametric avatar/mannequin | #203/#208 | active P0 |
| Canonical GUI acceptance | #155/#143/#229 | active P0 follow-up |
| Pattern authoring parity | #162 | active P1 after P0 |

## Current P0 acceptance status

1. Workbench registration/internal IDs: **passed**.
2. Native Sketcher authority and save/reload: **passed in canonical E2E**.
3. Persisted semantic seams and M:N SewingNetwork: **passed in canonical E2E**.
4. Particle-distance quality changes deterministic derived mesh density: **passed in headless regression and canonical E2E**.
5. Upstream edit invalidation and re-simulation: **passed in canonical E2E**.
6. Real FreeCAD/Xvfb canonical workflow: **terminal-green** for the merged #229 gate.

## Rules

1. Sketcher geometry is source geometry; PatternPiece is the semantic garment object.
2. PatternIR is solver-neutral and preserves native curve identity/connectivity.
3. Sewing references use semantic IDs/signatures, never fragile insertion-order edge numbers.
4. Simulation consumes derived geometry and invalidates/rebuilds deterministically after source edits.
5. Prefer native FreeCAD Sketcher/Part/Mesh/TechDraw/document dependencies over parallel CAD infrastructure.
6. Every P0 feature requires headless tests plus real FreeCAD smoke/Xvfb coverage.
7. Keep one canonical CI workflow; do not create push-triggered workflow variants.

## Next supervisor sequence

1. Integrate the parametric human mannequin into the Simulation/Avatar document model with a stable collision API and canonical fitting test.
2. Complete curved/M:N Sewing UX: correspondence editing, reverse/alignment, length checks and repair states.
3. Replace legacy drafting as the default Pattern UI with native Sketcher commands while retaining migration support.
4. Add explicit seam-allowance/notch/grainline/internal-mark derived features to the native Pattern workflow.
5. Finish production round-trip/export acceptance and package/install validation.
6. Re-audit every remaining open issue and close stale architecture branches before release.

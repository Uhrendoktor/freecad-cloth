# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

Initial open PRs/issues were audited before new implementation. Stale stacked branches were closed; validated work was rebased and merged only after terminal-green canonical CI.

### Current architecture gates

- **P0-A Pattern authoring:** native `Sketcher::SketchObject` is authoritative for linked PatternPieces. PatternIR preserves native curve kind and endpoint connectivity. The native Sketcher authority gate is merged and verified by real FreeCAD/Xvfb.
- **P0-B Sewing:** semantic seam references and authoritative PatternPiece Show 2D are merged. Remaining work: curved/M:N sewing UX, seam editing/length validation, invalid-reference UX, and dependency invalidation.
- **P0-C Simulation:** quality/material property model and avatar collision path exist. Current work is making particle-distance quality affect authored-pattern mesh density deterministically and finishing the parametric avatar/fitting path.
- **P0-D Acceptance:** canonical FreeCAD/Xvfb smoke exists. Next gate upgrades it from direct PatternPiece construction to three native Sketcher-backed pieces, curved seam, save/reload, upstream edit invalidation, quality-density change, and deterministic re-simulation.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | done |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Simulation quality/material density | #145 | active P0 |
| Parametric avatar/mannequin | #203/#208 | active P0 |
| Canonical GUI acceptance | #155/#143 | active P0 |
| Pattern authoring parity | #162 | active P1 after P0 |

## Rules

1. Sketcher geometry is source geometry; PatternPiece is the semantic garment object.
2. PatternIR is solver-neutral and preserves native curve identity/connectivity.
3. Sewing references use semantic IDs/signatures, never fragile insertion-order edge numbers.
4. Simulation consumes derived geometry and must invalidate/rebuild deterministically after source edits.
5. Prefer native FreeCAD Sketcher/Part/Mesh/TechDraw/document dependencies over parallel CAD infrastructure.
6. Every P0 feature requires headless tests plus real FreeCAD smoke/Xvfb coverage.
7. Keep one canonical CI workflow; do not create push-triggered workflow variants.

## Next supervisor sequence

1. Merge/review the simulation particle-distance mesh-density gate and add GUI persistence coverage.
2. Rebase/integrate the parametric human mannequin into the Simulation/Avatar document model; preserve a stable collision service API.
3. Replace `tests/freecad_e2e.py` with the real Sketcher-backed 3-piece garment acceptance fixture and verify save/reload/edit→seam→mesh→simulation invalidation.
4. Complete Sewing UI for curved/M:N correspondences, reverse/alignment, length checking, and invalid-reference repair.
5. Replace legacy drafting as the default Pattern UI with native Sketcher commands; retain it only as migration support.
6. Finish production round-trip/export acceptance and release packaging.
7. Re-audit all open issues and update this status file before release.

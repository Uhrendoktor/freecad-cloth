# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

Initial open PRs/issues were audited before new implementation. Stale stacked branches were closed; validated work was rebased and merged only after terminal-green canonical CI.

### Current architecture gates

- **P0-A Pattern authoring:** native `Sketcher::SketchObject` is authoritative for linked PatternPieces. PatternIR preserves native curve kind and endpoint connectivity. The native Sketcher authority gate is merged and verified by real FreeCAD/Xvfb.
- **P0-B Sewing:** semantic seam references and authoritative PatternPiece Show 2D are merged. Remaining work: curved/M:N sewing UX, seam editing/length validation, invalid-reference UX, and dependency invalidation.
- **P0-C Simulation:** quality/material property model and avatar collision path exist. Particle-distance mesh-density work is implemented; its canonical regression is being verified in replacement PR #227 after the #224 CI audit.
- **P0-D Acceptance:** canonical FreeCAD/Xvfb smoke already proves all three registered workbench toolbars/task panels. The garment acceptance fixture now targets internal workbench IDs and is the next real integration gate.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | done |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Simulation quality/material density | #145/#227 | active P0 |
| Parametric avatar/mannequin | #203/#208 | active P0 |
| Canonical GUI acceptance | #155/#143/#227 | active P0 |
| Pattern authoring parity | #162 | active P1 after P0 |

## CI audit findings

PR #224's first canonical run failed for two concrete reasons:

1. `tests/test_simulation_quality.py` imported `FreeCAD` indirectly from `SimulationMeshQuality.py`, although the test is intentionally part of the plain-Python matrix. The mesh helper is now FreeCAD-independent unless a real placement transformation is supplied.
2. The GUI screenshot phase reached the real FreeCAD runtime but the canonical E2E fixture called display labels (`Cloth Pattern`, etc.) rather than the registered internal IDs. The replacement fixture uses `ClothPatternWorkbench`, `ClothSewingWorkbench`, and `ClothSimulationWorkbench`.

No solver behavior was weakened to make CI pass. The real-FreeCAD smoke remained green in the failed run.

## Rules

1. Sketcher geometry is source geometry; PatternPiece is the semantic garment object.
2. PatternIR is solver-neutral and preserves native curve identity/connectivity.
3. Sewing references use semantic IDs/signatures, never fragile insertion-order edge numbers.
4. Simulation consumes derived geometry and must invalidate/rebuild deterministically after source edits.
5. Prefer native FreeCAD Sketcher/Part/Mesh/TechDraw/document dependencies over parallel CAD infrastructure.
6. Every P0 feature requires headless tests plus real FreeCAD smoke/Xvfb coverage.
7. Keep one canonical CI workflow; do not create push-triggered workflow variants.

## Next supervisor sequence

1. Get #227's complete canonical CI terminal-green; audit every job including real FreeCAD/Xvfb.
2. Merge the quality-density gate only after real FreeCAD E2E proves three Sketcher-backed pieces, seams, quality change, save/reload, upstream edit, and re-simulation.
3. Rebase/integrate the parametric human mannequin into the Simulation/Avatar document model; preserve a stable collision service API.
4. Complete Sewing UI for curved/M:N correspondences, reverse/alignment, length checking, and invalid-reference repair.
5. Replace legacy drafting as the default Pattern UI with native Sketcher commands; retain it only as migration support.
6. Finish production round-trip/export acceptance and release packaging.
7. Re-audit all open issues and update this status file before release.

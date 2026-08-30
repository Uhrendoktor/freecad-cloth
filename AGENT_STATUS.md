# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

Initial PR/issue backlog was audited before new implementation. Stale stacked branches were closed; validated slices are merged only after terminal-green canonical CI. The current P0 gate is the integrated native-Sketcher → Sewing → Simulation workflow.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority for linked PatternPieces; PatternIR preserves curve kind and endpoint connectivity.
- **P0-B Sewing:** semantic seam references, Show 2D, M:N SewingNetwork, and task-panel invalid-reference rejection are merged.
- **P0-C Simulation:** quality/material properties, avatar collision source, and deterministic particle-distance mesh generation are implemented; integrated acceptance is active.
- **P0-D Acceptance:** canonical FreeCAD/Xvfb now targets registered Pattern/Sewing/Simulation workbenches, native Sketcher authority, persisted seams/M:N network, quality-density change, save/reload, upstream edit invalidation and re-simulation.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | done |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Sewing invalid-reference task acceptance | #226, merged | done |
| Simulation quality/material density | #145/#227 | active P0 |
| Parametric avatar/mannequin | #203/#208 | active P0 |
| Canonical GUI acceptance | #155/#143/#227 | active P0 |
| Pattern authoring parity | #162 | active P1 after P0 |

## Current P0 acceptance criteria

1. All three workbenches register under stable internal IDs and expose their expected toolbars/commands.
2. PatternPieces can acquire native Sketcher authority and survive save/reload.
3. Sewing persists semantic references and M:N networks.
4. Particle-distance quality changes authored simulation mesh density deterministically.
5. A source dimensional edit invalidates dependent sewing/simulation state and re-simulation succeeds.
6. The entire scenario passes in real FreeCAD under Xvfb; plain-Python tests remain FreeCAD-independent where intended.

## Rules

1. Sketcher geometry is source geometry; PatternPiece is the semantic garment object.
2. PatternIR is solver-neutral and preserves native curve identity/connectivity.
3. Sewing references use semantic IDs/signatures, never fragile insertion-order edge numbers.
4. Simulation consumes derived geometry and invalidates/rebuilds deterministically after source edits.
5. Prefer native FreeCAD Sketcher/Part/Mesh/TechDraw/document dependencies over parallel CAD infrastructure.
6. Every P0 feature requires headless tests plus real FreeCAD smoke/Xvfb coverage.
7. Keep one canonical CI workflow; do not create push-triggered workflow variants.

## Next supervisor sequence

1. Get the replacement simulation acceptance PR terminal-green and audit the complete run.
2. Merge only after the real FreeCAD E2E proves the integrated P0 criteria above.
3. Integrate the parametric human mannequin into the Simulation/Avatar document model with a stable collision API.
4. Complete curved/M:N Sewing UX: correspondence editing, reverse/alignment, length checks and repair states.
5. Replace legacy drafting as the default Pattern UI with native Sketcher commands while retaining migration support.
6. Finish production round-trip/export acceptance and package/install validation.
7. Re-audit every remaining open issue before release.

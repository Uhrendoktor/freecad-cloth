# Layered multi-piece garment simulation

## Objective
Deliver an inspectable twelve-panel layered outfit fixture that extends beyond the two-panel tunic and tests independently constructed shirt/skirt garment groups, including a deliberate shirt-hem/waistband overlap. Establish whether the current solver supports cloth-to-cloth contact; if not, implement and validate a bounded contact capability without misrepresenting the underlying PBD solver.

## Current evidence
- Base: `main` at `e6ab6e4a234b14bc314c24d456c2bf83c12e3e39`.
- Governing task: #2845. Woven-material follow-up: #2846. Product-gap context: #2759.
- `SimulationProxy._build_pattern_scene` already builds a combined particle model from multiple PatternPieces and semantic seams.
- `PositionBasedDynamicsBackend._build` creates one PBD triangle model and one rigid-body SDF target.
- Upstream PBD 2.2.2 `DistanceFieldCollisionDetection.cpp` explicitly defers deformable self-collision and skips triangle-model targets in its current distance-field pair filter.
- The current backend uses XPBD distance constraints and hard-coded scalar coefficients; the saved fabric UI fields are not presently a calibrated woven/orthotropic material contract.

## Architecture
- Keep Sketcher geometry, PatternPiece identity, PatternIR, and semantic sewing authoritative.
- Treat a garment as a seam-connected component; shirt and skirt remain separate components and are never stitched together.
- Keep DrapeTarget as the authoritative body-collision source.
- Any added inter-garment contact layer must operate on exact solver particle/triangle identities, preserve pins and sewn seams, and report measured contacts plus residual requested-clearance deficits after both cloth and body projections. A positive deficit is not signed volumetric intersection depth.
- Extend the existing scene-understanding dossier rather than adding a parallel reporting system.

## Scope
- Build a native-FreeCAD longline-shirt/A-line-skirt fixture with a separately sewn waistband; distinguish this feasibility fixture from a graded production shirt pattern.
- Add tests for independent garment grouping and inter-cloth geometric contact.
- Prototype and validate the smallest defensible two-sided contact mechanism if native pyPBD cannot provide it.
- Add garment/group/piece provenance and contact measurements to the existing diagnostic evidence.
- Capture actual motion and six-side rendered evidence through the canonical FreeCAD workflow.

## Non-goals
- No yarn-level simulation, parametric fabric-grid authoring UI, or claims of calibrated woven-fabric behavior in this milestone.
- Do not weaken tunic/avatar/seam/collision/visual thresholds or add a second workflow.
- Do not count one-way rigid proxy collision, visual overlap, or mere sewing constraints as cloth-to-cloth interaction.

## Implementation steps
1. Create deterministic headless contact/group controls and inspect current solver boundaries.
2. Add a real FreeCAD outfit fixture with independently sewn shirt and skirt groups; first validate pattern/sewing and save/reload.
3. Implement the minimal two-sided inter-cloth contact path with acceleration, adjacency exclusions, pin preservation and seam reconciliation; measure cost and failure modes.
4. Extend scene dossier and metrics with stable garment-group IDs, contact pairs, gap/penetration and stage status.
5. Run focused tests, real FreeCAD/Xvfb acceptance, exact-head canonical checks, and visually review motion plus six sides.
6. Record any concrete spatial-interpretation failure as a reproducible issue and improve the dossier/tests that address it.

## Verification
- Unit/property tests for group derivation, candidate generation, two-sided contact, parallel/crossing and coincident sheets, no-contact controls, pins, seam groups, final post-body residual measurement, finite-state and invalid input.
- Real FreeCAD pattern/sewing construction and save/reload.
- PBD integration using the supported Python 3.12 runtime.
- Actual rendered front/rear/left/right/top/bottom and checkpoint motion at steps 1, 15 and 60 from the same exact commit.
- Independent numeric contact evidence and human visual review.

## Falsifier / stop condition
Stop or re-scope the contact prototype if sheets still pass through one another in crossing controls, if projection breaks sewn seams or moves pins, if collision measurements disagree with rendered geometry, or if required performance is impractical. A multi-piece drape without validated inter-cloth interaction must be reported as partial.

## Result
In progress. The fixture now requires an intentional shirt/waistband overlap and a flared A-line skirt. Residual cloth-pair clearance is re-measured after the final mannequin projection; exact-head FreeCAD/Xvfb and visual results remain pending.

# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The initial PR/issue backlog and all open implementation PRs were audited before new work. PR #217 (task-panel transaction), rebased replacement #239 (Sewing selection validation), PR #238 (curved-seam correspondence validation), PR #249 (persistent parametric mannequin), and PR #251 (first-class DrapeTarget) are merged only after terminal-green canonical CI. Stale avatar/status/drape branches (#208, #216, #234, #237) were closed as superseded.

The roadmap was reworked around the end-to-end product: native Sketcher pattern authoring, semantic sewing, first-class human/general drape targets, and a production-oriented simulation workbench. See `docs/ROADMAP_2026_REPLAN.md`.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority for linked PatternPieces; PatternIR preserves curve kind and endpoint connectivity.
- **P0-B Sewing:** semantic seam references, Show 2D, M:N SewingNetwork, task-panel invalid-reference rejection, and reusable curved correspondence validation are merged. GUI repair integration remains next.
- **P0-C Human fitting:** persistent anthropometric mannequin with deterministic derived geometry, landmarks, pose, skin offset and collision proxy is merged and covered by canonical FreeCAD/Xvfb.
- **P0-D Drape target:** persistent target-neutral DrapeTarget for mannequin and arbitrary FreeCAD Shape/Mesh is merged; source geometry, Placement, tessellation and collision settings participate in deterministic signatures. Simulation UI uses the existing CollisionSurface adapter.
- **P0-E Simulation:** quality/material properties and deterministic particle-distance mesh generation are implemented; lifecycle/status, target-aware diagnostics and production simulation UX remain follow-up integration tasks.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | baseline done; release regression follow-up |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Sewing invalid-reference task acceptance | #226, merged | done |
| Curved seam correspondence validator | #238 | done; GUI integration in #247 |
| Simulation quality/material density | #145/#229 | active P0 integration |
| Parametric avatar/mannequin | #203/#249 | done baseline; richer pose/measurement UI follow-up |
| General DrapeTarget | #228/#251 | done baseline; solver migration/diagnostics follow-up |
| Canonical GUI acceptance | #155/#143/#229 | active P0 follow-up |
| Pattern authoring parity | #162 | active P1 |

## Current acceptance status

1. Workbench registration/internal IDs: **passed**.
2. Native Sketcher authority and save/reload: **passed in canonical E2E**.
3. Persisted semantic seams and M:N SewingNetwork: **passed in canonical E2E**.
4. Curved seam correspondence validator: **merged and terminal-green; GUI repair integration pending**.
5. Particle-distance quality changes deterministic derived mesh density: **passed**.
6. Upstream edit invalidation and re-simulation: **passed in canonical E2E**.
7. Parametric mannequin creation, measurement change, pose, skin offset, collision proxy and save/reload: **passed in canonical FreeCAD/Xvfb**.
8. DrapeTarget creation for mannequin and arbitrary FreeCAD geometry, deterministic source signature and Simulation UI registration: **passed in canonical FreeCAD/Xvfb**.
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

1. Integrate curved correspondence into the Sewing task panel with actionable repair states, reverse/alignment controls and M:N editing (#247).
2. Add simulation lifecycle/status and target-aware invalidation so DrapeTarget is authoritative rather than only bridged through AvatarCollision.
3. Replace legacy drafting as the default Pattern UI with native Sketcher commands while retaining migration support.
4. Add explicit seam-allowance/notch/grainline/internal-mark derived features and production size/grading semantics.
5. Finish canonical create -> sew -> arrange -> drape -> edit -> invalidate -> rebuild -> save/reload acceptance.
6. Finish TechDraw/DXF/SVG round-trip and package/install validation.
7. Benchmark optional native solvers only after all P0/P1 gates are green.

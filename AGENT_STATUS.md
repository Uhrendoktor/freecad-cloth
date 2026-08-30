# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The initial PR/issue backlog and all open implementation PRs were audited before new work. The current audit merged the audited icon, GUI screenshot, simulation lifecycle, transactional M:N editor, and curved-seam repair slices after reviewing diffs and resolving stale/draft PR mechanics. Draft PRs that could not be transitioned because the GitHub connector's ready-for-review mutation fails with a GraphQL schema error were closed with explicit supersession reasons and recreated as non-draft PRs from the same heads.

The roadmap was reworked around the end-to-end product: native Sketcher pattern authoring, semantic sewing, first-class human/general drape targets, arrangement, and a production-oriented simulation workbench. See `docs/ROADMAP_2026_REPLAN.md` and `docs/RESEARCH_2026_CLO_FREECAD.md`.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority for linked PatternPieces; PatternIR preserves curve kind and endpoint connectivity.
- **P0-B Sewing:** semantic seam references, Show 2D, M:N SewingNetwork, task-panel invalid-reference rejection, curved correspondence validation, transactional M:N task-panel editing, and actionable reversible/range repair are implemented.
- **P0-C Human fitting:** persistent anthropometric mannequin with deterministic derived geometry, landmarks, pose, skin offset and collision proxy is merged and covered by canonical FreeCAD/Xvfb.
- **P0-D Drape target:** persistent target-neutral DrapeTarget for mannequin and arbitrary FreeCAD Shape/Mesh is merged; authoritative status now detects stale source/placement/tessellation state.
- **P0-E Simulation:** quality/material properties, deterministic particle-distance mesh generation, explicit lifecycle commands, and target-aware status reporting are implemented; target-driven collision rebuild integration and production simulation UX remain follow-up work.

## Active workstreams

| Workstream | Issue/PR | Status |
|---|---|---|
| PatternIR curve/connectivity | #165/#174/#188, merged #206 | done |
| Semantic seam references | #169, merged #200 | done |
| Production export validation | #163/#147, merged #209 | baseline done; release regression follow-up |
| Native Sketcher authority | #165/#170, merged #215 | done |
| Workbench lifecycle/boundaries | #212, merged #218 | done |
| Sewing invalid-reference task acceptance | #226, merged | done |
| Curved seam correspondence validator | #238/#247/#279 | validator + repair UX merged; canonical verification pending |
| M:N Sewing task-panel transaction | #241/#274 | merged; canonical verification pending |
| DrapeTarget status/authority | #228/#251/#276 | status/refresh contract active; solver collision integration next |
| Simulation quality/material density | #145/#229 | active P0 integration |
| Simulation lifecycle/status | #261/#271 | merged; target-aware reporting now implemented |
| Parametric avatar/mannequin | #203/#249 | done baseline; richer pose/measurement UI follow-up |
| General DrapeTarget | #228/#251 | done baseline; #276 solver-authority/diagnostics follow-up |
| Canonical GUI acceptance | #155/#143/#229/#278 | active P0 |
| Pattern authoring parity | #162/#277 | active P0 production minimum then P1 grading |
| Production 2D export/package | #163/#147 | release regression follow-up |

## Current acceptance status

1. Workbench registration/internal IDs: **passed**.
2. Native Sketcher authority and save/reload: **passed in canonical E2E**.
3. Persisted semantic seams and M:N SewingNetwork: **passed in canonical E2E**.
4. Curved seam correspondence validator and repair command: **implemented; canonical verification pending**.
5. Transactional M:N task-panel editor: **merged; canonical verification pending**.
6. Particle-distance quality changes deterministic derived mesh density: **passed**.
7. Explicit Simulation Step/Run/Reset lifecycle contract: **merged; canonical verification pending**.
8. Simulation status now reports DrapeTarget missing/disabled/unbuilt/stale/ready states: **implemented; canonical verification pending**.
9. Upstream edit invalidation and re-simulation: **passed in canonical E2E**.
10. Parametric mannequin creation, measurement change, pose, skin offset, collision proxy and save/reload: **passed in canonical FreeCAD/Xvfb**.
11. DrapeTarget creation for mannequin and arbitrary FreeCAD geometry, deterministic source signature and Simulation UI registration: **passed baseline; authoritative target integration pending**.
12. Full FreeCAD-window GUI screenshot capture: **merged; current canonical verification pending**.
13. Production export/package/install acceptance: **not yet release-complete**.

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

1. Finish #276 by making Simulation collision rebuild consume the persistent DrapeTarget directly rather than the legacy AvatarProxy path.
2. Build #278 as the canonical public-workbench end-to-end garment release fixture.
3. Add persistent seam-allowance/notch/grainline/internal-mark PatternMarks (#277), keeping Sketcher authoritative.
4. Replace legacy drafting as the default Pattern entry point with native Sketcher commands while retaining migration support.
5. Finish TechDraw/DXF/SVG round-trip and package/install validation.
6. Benchmark optional native solvers only after all P0/P1 gates are green.

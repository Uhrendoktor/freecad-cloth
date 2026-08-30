# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The initial PR/issue backlog and all open implementation PRs were audited before new work. The audit merged the icon, GUI screenshot, simulation lifecycle, transactional M:N editor, curved-seam repair, DrapeTarget-status, and CI-control-plane documentation slices after reviewing diffs and resolving stale/draft PR mechanics. Draft PRs that could not be transitioned because the GitHub connector's ready-for-review mutation fails with a GraphQL schema error were closed with explicit supersession reasons and recreated as non-draft PRs from the same heads.

The roadmap was reworked around the end-to-end product: native Sketcher pattern authoring, semantic sewing, first-class human/general drape targets, arrangement, and a production-oriented simulation workbench. See `docs/ROADMAP_2026_REPLAN.md` and `docs/RESEARCH_2026_CLO_FREECAD.md`.

CI audit finding: recent `pull_request` runs were absent for stale/conflicted PRs; GitHub documents that `pull_request` workflows do not run while a PR has merge conflicts. A clean-branch probe was merged as `docs/CI_CONTROL_PLANE.md`. The canonical workflow remains the only workflow. Current main commits made through the repository contents API do not themselves provide fresh Actions execution evidence, so release gates that require FreeCAD/Xvfb remain explicitly marked pending until a clean PR run is observed.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority for linked PatternPieces; PatternIR preserves curve kind and endpoint connectivity.
- **P0-B Sewing:** semantic seam references, Show 2D, M:N SewingNetwork, task-panel invalid-reference rejection, curved correspondence validation, transactional M:N task-panel editing, and actionable reversible/range repair are implemented.
- **P0-C Human fitting:** persistent anthropometric mannequin with deterministic derived geometry, landmarks, pose, skin offset and collision proxy is merged and covered by prior canonical FreeCAD/Xvfb evidence.
- **P0-D Drape target:** persistent target-neutral DrapeTarget for mannequin and arbitrary FreeCAD Shape/Mesh is merged; authoritative status detects stale source/placement/tessellation/collision settings.
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
| Curved seam correspondence + repair | #238/#247/#279 | implementation merged; canonical verification pending |
| M:N Sewing task-panel transaction | #241/#274 | implementation merged; canonical verification pending |
| DrapeTarget status/authority | #228/#251/#281 | status/refresh contract merged; solver collision integration next |
| Simulation quality/material density | #145/#229 | active P0 integration |
| Simulation lifecycle/status | #261/#271 | completed; issue #261 closed |
| Parametric avatar/mannequin | #203/#249 | done baseline; richer pose/measurement UI follow-up |
| General DrapeTarget | #228/#251/#276 | baseline merged; #276 solver-authority/diagnostics remains open |
| Canonical GUI acceptance | #155/#143/#229/#278 | active P0; existing E2E is broad but new release-gate assertions remain to be verified in canonical CI |
| Pattern authoring parity | #162 | active P1/P0 production audit; existing PatternMarks baseline is already in main |
| Production 2D export/package | #163/#147 | release regression follow-up |
| UI consistency | #267/#258/#252/#120/#126 | open follow-up audit; do not start until P0 workflow is stable |

## Current acceptance status

1. Workbench registration/internal IDs: **passed**.
2. Native Sketcher authority and save/reload: **passed in canonical E2E**.
3. Persisted semantic seams and M:N SewingNetwork: **passed in canonical E2E**.
4. Curved seam correspondence validator and repair command: **implemented; canonical verification pending**.
5. Transactional M:N task-panel editor: **merged; canonical verification pending**.
6. Particle-distance quality changes deterministic derived mesh density: **passed**.
7. Explicit Simulation Step/Run/Reset lifecycle contract: **merged; canonical verification pending**.
8. Simulation status reports DrapeTarget missing/disabled/unbuilt/stale/ready states: **implemented; canonical verification pending**.
9. Upstream edit invalidation and re-simulation: **passed in canonical E2E**.
10. Parametric mannequin creation, measurement change, pose, skin offset, collision proxy and save/reload: **passed in canonical FreeCAD/Xvfb**.
11. DrapeTarget creation for mannequin and arbitrary FreeCAD geometry, deterministic source signature and Simulation UI registration: **passed baseline; authoritative target integration pending**.
12. Full FreeCAD-window GUI screenshot capture: **merged; current canonical verification pending**.
13. PatternMarks baseline (Notch/Grainline/Internal Mark) is already present in main; richer derived mark geometry/Fold/Dart remains future work.
14. Production export/package/install acceptance: **not yet release-complete**.

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
2. Rework #278 as a minimal diff against the existing E2E fixture and verify it in a clean canonical FreeCAD/Xvfb PR run.
3. Close the remaining release-blocking Pattern/Sewing/Simulation audit gaps from #143/#155/#162 before starting optional solver work.
4. Finish TechDraw/DXF/SVG round-trip and package/install validation.
5. Only after P0/P1 gates are green, address UI consistency #267/#258/#252 and benchmark optional native solvers (#148).

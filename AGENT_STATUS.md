# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The supervisor audited all currently open issues and PRs before accepting new implementation work. Merged historical slices remain #314, #319, #311 and #317. Duplicate/stale DrapeTarget PR #339 and superseded CI-harness PR #343 were closed with explicit reasons. Supervisor roadmap/replan PR #348 is merged to main.

## Replanned release sequence

1. **P0-A CI/public-workbench gate:** canonical job scheduling is deterministic; the current blocker is a real FreeCAD/Xvfb simulation-fixture failure tracked in #347. Do not weaken the assertion or skip GUI coverage.
2. **P0-B DrapeTarget authority (#322/#346):** persistent target-neutral lifecycle, safe recompute, explicit Refresh, public Step/Run preflight, save/reload. #346 must be re-cut without its workflow workaround and must route QualitySimulationProxy through DrapeTarget authority.
3. **P0-C Canonical garment E2E (#278/#155/#143):** native Pattern -> Sewing -> arrangement -> DrapeTarget -> Simulation -> save/reload -> invalidation -> refresh -> deterministic re-simulation.
4. **P0-D Simulation quality (#145/#159/#161):** particle distance/mesh density, fabric physics, solver controls and collision settings must materially affect derived state and persist. #347 is the immediate mesh-density integration slice.
5. **P0-E Release UX/persistence (#267):** consistent task-panel hierarchy, native FreeCAD selection/undo/recompute/save/reload, explicit diagnostics.
6. **P1 Pattern architecture/production (#162/#165/#297/#298/#147/#163):** native Sketcher authority, stable semantic topology, explicit repair, curved manufacturability, export/TechDraw.
7. **P2 optional solver benchmark (#148)** only after P0/P1 are green.

## Research decisions

CLO 2026 confirms that release-relevant garment semantics include persistent pattern properties, a Property Editor across patterns/sewing/fabric/avatar/simulation, persistent 3D arrangement, Smart Arrangement, particle-distance/quality controls, CPU/GPU simulation modes, Segment/Free/1:N/M:N sewing, directional/reversal behavior and explicit seam validation/repair workflows. FreeCAD's native Sketcher already provides geometric/dimensional constraints and expressions; Cloth should not duplicate that solver.

The detailed UI/command matrix and dependency graph are documented in `docs/ROADMAP_2026.md` on main.

## Current CI finding

Canonical run #816 scheduled all required jobs. Python 3.10/3.11/3.12 and real FreeCAD smoke passed. Xvfb reached Pattern and Sewing, then failed at the Simulation fixture because the arranged garment panels had fewer than the required useful facets. This is tracked as #347.

The release invariant is strict: fix the fixture or underlying mesh lifecycle; never remove the assertion, skip Simulation, or replace the public-workbench workflow with a utility-only test.

## DrapeTarget invariant

Target edit -> persistent STALE with reason -> ordinary document recompute remains safe -> stale collision is never consumed -> Step/Run are blocked -> Refresh rebuilds collision -> READY_FOR_SIMULATION -> simulation may advance. Reset remains available while stale. QualitySimulationProxy must share this authority.

## Architecture gates

- **Pattern:** native Sketcher geometry authority; stable semantic edge references.
- **Sewing:** persistent semantic seam/network references, curved correspondence, M:N/free sewing, direction/reversal and explicit repair.
- **Fitting/Arrangement:** persistent 3D arrangement state and configurable human target.
- **DrapeTarget:** target-neutral persistent collision authority with explicit lifecycle.
- **Simulation:** quality-controlled derived mesh/solver state; stale target cannot simulate.

## Active supervised work

- **#347:** repair Simulation GUI fixture/mesh-density failure under real FreeCAD/Xvfb; preserve coarse PatternMesh API and add simulation-specific refinement driven by quality/particle distance.
- **#346:** DrapeTarget recompute-safety candidate; audit after #347 and canonical green checks. Remove workflow workaround and avatar-only collision bypass.
- **#345/#332:** workbench registration contract coverage; audit after canonical GUI gate is green.
- **#340:** native Sketcher acceptance; audit for real FreeCAD/Xvfb compatibility.
- **#336:** explicit Pattern semantic-topology repair UI; fix Qt OK/Cancel contract and re-cut from current main.
- **#330/#335/#338:** focused UX/command-label slices; preserve scope and avoid unrelated architecture changes.
- **#258:** Sewing grouped-menu implementation remains in progress and must retain the stable toolbar contract.
- **#145/#297/#298:** supervised subagent slices with dedicated branches; inspect their PR/CI state before accepting.

## Coordination rules

- Update this file at every slice start/handoff.
- One canonical GitHub Actions workflow only.
- Re-cut stale branches from current main; do not merge parallel implementations of the same contract.
- Public FreeCAD commands/task panels/document objects are the acceptance surface.
- A milestone is complete only after canonical CI is green and merged-main verification is green.

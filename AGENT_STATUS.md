# Agent status

Compact live supervisor/recovery record. Do not use this file as an experiment log; detailed evidence belongs in the governing issue/PR.

## Repository
- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Last audited main HEAD: `cb0e94965190b59f398824b66f0cc804828ec59b`
- Reusable CI engine: `.github/workflows/canonical-execution.yml`; entry points: `commit-validation.yml` (fast PR), `merge-validation.yml` (full merge-queue validation), and `main-publication.yml` (main-only documentation publication).
- Root coordination ledger: #2492.
- No production Tissu contact repair is merged.

## Current open diagnostic/research lanes
- #2577 — independent human challenge of a proposed Tissu substep production remedy.
- #2576 — bounded Tissu substep probe (16/20/32).
- #2575 — avatar collision coarsening/coverage audit.
- #2571 — diagnosis of the remaining canonical tunic Tissu collapse.
- #2554 — backend-parity audit for Tissu/XPBD stitch replacement semantics.
- #2545 — recorded TissuBackend set_stitches semantic divergence.

These lanes are intentionally narrow. Inspect only the lane relevant to the current task.

## Completed / historical diagnostic lanes
- #2537 — cube complexity ladder; completed.
- #2482 — avatar complexity ladder; completed.
- #2535 — tunic initial/first-step collision diagnostic; completed.
- #2540 — canonical tunic stitch handoff diagnostic; completed.
- #1017 — completed release project criterion; historical release context only.

## Current-state warning
The repository contains historical release-closeout documents and evidence. They describe what was validated at a particular point in time and are not a substitute for current-main state. The current PositionBasedDynamics runtime is authoritative. Historical Tissu diagnostic lanes and older release-closeout screenshots are context only; do not infer current simulation behavior from them.


Current task: migrating the production simulation runtime from Tissu to PositionBasedDynamics (pyPBD 2.2.2). The DrapeTarget/CollisionSurface boundary remains authoritative.

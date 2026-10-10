# Agent status

Compact live supervisor/recovery record. Do not use this file as an experiment log; detailed evidence belongs in the governing issue/PR.

## Repository
- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Last reconciled main HEAD: `52518611f6c5df79e3648302e9f105eb841d01c6` (2026-10-10).
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one canonical workflow.
- Root coordination ledger: #2492. Its Tissu-era active-lane list must not be treated as current runtime authorization.
- Current runtime: `PositionBasedDynamicsBackend` using pyPBD 2.2.2 is the only runtime backend; `tests/test_backend_authority.py` asserts that `XPBDBackend` is absent and PositionBasedDynamics is the production implementation.
- The `DrapeTarget` / `CollisionSurface` boundary remains authoritative.

## Historical Tissu diagnostic lanes
The following open issues were created against the former Tissu runtime and were last updated on 2026-10-03 without assignees, comments, or linked implementation PRs:
- #2577 — human challenge of a Tissu substep remedy.
- #2576 — Tissu substep probe (16/20/32).
- #2575 — avatar collision coarsening/coverage audit for the Tissu failure hypothesis.
- #2571 — canonical Tissu tunic-collapse diagnosis.
- #2554 — Tissu/XPBD stitch replacement-semantics parity.
- #2545 — TissuBackend stitch-accumulation finding.

These are historical evidence, not active tasks against current main. Do not dispatch or resume them as-is. Re-open the question only through a new, narrowly scoped issue with an exact current-main SHA and a falsifiable hypothesis if current PositionBasedDynamics behavior demonstrates the same concern. The parent ledger #2492 should be reconciled to this runtime boundary.

## Current-state warning
Historical release-closeout documents, closed issues, old branches, and old workflow runs are evidence for their recorded source revisions only. The current PositionBasedDynamics runtime and exact-head canonical runs are authoritative. Do not infer current simulation behavior from Tissu-specific diagnostics or older screenshots.

## Current focus
Keep the production simulation boundary backend-neutral, preserve existing acceptance thresholds and workflow topology, and require exact-head canonical validation plus rendered evidence for simulation changes. The open material-control audit (#2602) also needs to be assessed against the current PBD runtime; do not invent physical-to-solver numeric mappings without documented semantics.

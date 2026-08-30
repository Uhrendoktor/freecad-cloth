# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The supervisor has completed the required PR/issue audit for the current integration slice. Merged: #314 Sewing command-group recovery, #319 Sewing GUI activation-stall recovery, #311 transactional M:N regression coverage, and #317 actionable seam-repair diagnostics. Stale/duplicate branches were closed with reasons and their useful proposals retained in the issue/roadmap backlog.

The project is now in the P0-1 DrapeTarget lifecycle slice. Current supervisor branch: `agent/drapetarget-authority-current-20260830`.

## Replanned release sequence

1. **P0-0 Sewing GUI integration:** merged; canonical FreeCAD/Xvfb verification remains required.
2. **P0-1 DrapeTarget authority (#276/#289/#284/#322):** persistent lifecycle, target-neutral public commands, explicit Refresh, stale preflight, safe recompute, save/reload.
3. **P0-2 Canonical garment E2E (#278/#155/#143):** native Pattern -> Sewing -> fitting/arrangement -> DrapeTarget -> Simulation -> save/reload -> upstream edit/invalidation -> refresh -> deterministic re-simulation.
4. **P0-3 Simulation behavior (#145/#159/#161):** quality/material/collision controls materially affect derived topology/backend state and persist.
5. **P0-4 Release UX/persistence:** task panels, selection, undo/recompute, save/reload, error/cancel behavior, and no scripting-only acceptance paths.
6. **P1 Pattern/export/package (#162/#165/#297/#298/#147/#163).**
7. **P2 optional solver benchmark (#148)** only after P0/P1 are green.

## Research decisions

CLO/Marvelous Designer behavior makes semantic sewing, visible correspondence/reversal/repair, arrangement state, target-aware collision and particle-distance quality controls release semantics. FreeCAD Sketcher/Part/TechDraw should remain the geometry/constraint/export kernels; Cloth owns garment meaning and lifecycle. The native Sketcher authority proposal from closed #321 is retained for P1 rather than merged as a stale branch.

## P0-1 current finding

The bounded DrapeTarget re-cut in #320 adds explicit `VALID/STALE/INVALID/REFRESHING/READY_FOR_SIMULATION` lifecycle state, public Refresh, target-neutral attachment and Simulation preflight/task-panel recovery. Supervisor review then found a remaining correctness blocker: current `SimulationObjects._collision_for_scene()` raises during ordinary document recompute when a target becomes stale. This is tracked in #322 and must be repaired before #320 is accepted.

The invariant is strict: target edit -> STALE with reason; recompute remains safe; no stale collision surface is consumed; Step/Run are blocked; Refresh rebuilds collision state; Reset remains available.

## Architecture gates

- **Pattern:** native Sketcher geometry authority; stable semantic edge references.
- **Sewing:** persistent semantic seam/network references, curved correspondence, M:N and repair UX.
- **Fitting:** persistent mannequin/arrangement state.
- **DrapeTarget:** target-neutral persistent collision authority with explicit lifecycle.
- **Simulation:** disposable derived topology/solver state; stale target cannot be simulated.

## Coordination rules

- Update this file at slice start/handoff.
- One canonical GitHub Actions workflow only.
- Do not merge stale/non-mergeable branches; re-cut from current main and preserve proposals.
- Public FreeCAD commands/task panels/document objects are the acceptance surface.
- A milestone is not complete until canonical CI is green and merged-main verification is green.

## Subagent slice — #322

Claimed by `Uhrendoktor` on 2026-08-30. Branch: `agent/drapetarget-recompute-fix-20260830`.

Implementation direction: repair the stale-target lifecycle directly in `SimulationObjects` rather than carrying forward the superseded runtime monkey-patch from #290/#292. Ordinary recompute now records persistent target status/reason, skips stale collision consumption, and marks simulation non-finite without advancing solver steps. Public Step/Run are explicitly gated on a current DrapeTarget; Reset remains available. Focused regression coverage covers placement invalidation, safe recompute, no stale collision consumption, and public command gating.

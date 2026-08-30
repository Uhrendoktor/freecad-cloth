# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The supervisor audited the open PR/issue set before this slice, merged the focused Sewing GUI registration repair (#314) and transactional M:N regression coverage (#311), and re-cut/merged the seam-repair diagnostic fix as #317. Duplicate/stale registration, Pattern, DrapeTarget and CI branches were closed with reasons; their proposals remain in the roadmap/issues.

Current supervisor implementation branch: `agent/drapetarget-authority-current-20260830`.

## Replanned release sequence

1. **P0-0 Sewing GUI registration:** merged #314; verify on current main through canonical FreeCAD/Xvfb.
2. **P0-1 DrapeTarget authority:** this slice. Make DrapeTarget lifecycle explicit, keep public commands target-neutral, expose Refresh, and block simulation while stale.
3. **P0-2 Canonical garment E2E (#278/#155/#143):** Pattern -> Sewing -> fitting/arrangement -> DrapeTarget -> Simulation -> save/reload -> upstream edit -> stale -> refresh -> re-simulate.
4. **P0-3 Simulation behavior (#145/#159/#161):** quality/material/collision settings must change derived behavior and persist.
5. **P0-4 Release UX/persistence:** audit task panels, selection, undo/recompute, save/reload and remove scripting-only acceptance paths.
6. **P1 Pattern/export/package:** concrete #162/#298 authoring blockers, then production 2D export (#147/#163).
7. **P2 optional solver benchmark (#148):** only after P0/P1 are green.

## Research decisions

CLO/Marvelous Designer behavior confirms that semantic sewing, visible correspondence/reversal/repair, arrangement state, target-aware collision and particle-distance quality controls are product semantics, not utility features. FreeCAD Sketcher/Part/TechDraw remain the geometry/constraint/export kernels; Cloth owns garment meaning and lifecycle.

## Current DrapeTarget slice

`DrapeTarget.py` now has explicit persistent lifecycle states `VALID`, `STALE`, `INVALID`, `REFRESHING`, and `READY_FOR_SIMULATION`. Source geometry/placement/collision settings are rechecked through the existing deterministic source signature. `Refresh Drape Target` rebuilds the collision cache and returns the target to ready state.

Public Drape commands now attach `scene.DrapeTarget` directly, preserving `FreeCAD Geometry` versus `Mannequin`, and add `ClothDrape_RefreshTarget`. Simulation Step/Run activation and command execution require a ready DrapeTarget. The Simulation task panel exposes target state and a Refresh button.

This is intentionally a smaller re-cut than the superseded #304/#303 branches. Dependency classes for pattern/sewing/avatar/arrangement will be added only where the current document model can supply stable Links; no silent topology retargeting is allowed.

## Architecture gates

- **P0-A Pattern:** native Sketcher geometry is authoritative; Cloth stores semantic metadata.
- **P0-B Sewing:** persistent semantic seam/network references, curved correspondence, M:N and repair UX.
- **P0-C Fitting:** persistent mannequin and arrangement state.
- **P0-D DrapeTarget:** target-neutral persistent collision authority with explicit lifecycle.
- **P0-E Simulation:** disposable derived topology/solver state; stale target must block simulation and expose recovery.

## Coordination rules

- Update this file at slice start/handoff.
- One canonical GitHub Actions workflow only.
- Do not merge stale/non-mergeable branches; re-cut from current main and preserve the proposal.
- Public FreeCAD commands/task panels/document objects are the acceptance surface.
- A milestone is not complete until canonical CI is green and merged-main verification is green.

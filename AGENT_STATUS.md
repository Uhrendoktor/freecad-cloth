# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The project is being driven as three native FreeCAD workbenches: Cloth Pattern, Cloth Sewing, and Cloth Simulation. The authoritative acceptance path is public FreeCAD document objects, commands and task panels; utility-only scripts are not completion evidence.

## Current execution

- **CI control plane:** supervisor branch `agent/ci-control-plane-repair-20260830`, PR #294. The previous canonical run failed before scheduling any jobs. This branch reduces the workflow to the required Python, real FreeCAD and Xvfb acceptance jobs and makes pull-request event types explicit.
- **Python 3.12 regression:** the canonical Core and geometry stage exposed a headless `SewingCommands._ACTIVATION` import contract bug. The same failure was observed under Python 3.10 and 3.12 in run #33309390274; it is not Python-version-specific.
- **DrapeTarget:** PR #292 remains open and must not merge until canonical FreeCAD/Xvfb verifies stale-target recompute safety.
- **Sewing:** #275 remains the functional gate for curved correspondence, reversal/alignment diagnostics and transactional M:N editing.
- **End-to-end:** #278/#155 remain the release fixture gates.
- **Pattern:** #162 is the production-minimum audit; native Sketcher remains authoritative.
- **Avatar/drape:** #203 and #228 remain integrated through the target-neutral collision contract.

## Replanned order

1. Restore and verify canonical Actions scheduling.
2. Fix and verify the headless Sewing command activation contract across Python 3.10/3.11/3.12.
3. Verify/merge stale DrapeTarget lifecycle repair.
4. Verify curved/M:N sewing through the public task panel.
5. Audit/fix Pattern production minimum.
6. Integrate one public Pattern -> Sewing -> Arrange -> Drape -> Simulate -> Save/Reload -> Invalidate -> Refresh -> Simulate fixture.
7. Finish simulation quality/material controls and workbench UX.
8. Export/package/docs; optional solver backend benchmark last.

## CI regression finding

`SewingCommands._ACTIVATION` was defined inside the optional `import FreeCADGui` registration block. Plain CPython has no `FreeCADGui`, so importing the module headlessly left `_ACTIVATION` undefined and caused `test_sewing_repair.py` to raise `AttributeError`. The fix makes the activation mapping a module-level contract while keeping GUI command registration optional. The existing assertion remains intact and an explicit headless activation regression is added.

## Coordination rules

- Exactly one GitHub Actions workflow: `.github/workflows/canonical-execution.yml`.
- Update this file at implementation start/handoff.
- Do not silently retarget semantic references after topology changes.
- Compatibility layers may exist during migration but cannot become a second source of truth.
- Do not claim release readiness while canonical FreeCAD/Xvfb acceptance is unavailable or running.

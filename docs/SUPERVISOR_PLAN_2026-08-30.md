# Supervisor execution plan — 2026-08-30

## Current release gates

1. Restore canonical GitHub Actions scheduling and prove jobs are actually created.
2. Merge only after Python + real FreeCAD + Xvfb acceptance executes.
3. Complete stale DrapeTarget lifecycle (#289) and target-authoritative simulation.
4. Complete curved/M:N sewing public task-panel acceptance (#275).
5. Audit Pattern production minimum (#162): native Sketcher authority, semantic marks, allowances, stable references and invalidation.
6. Build one deterministic public-workbench garment fixture (#278/#155).
7. Integrate mannequin and arbitrary FreeCAD geometry through the target-neutral collision contract.
8. Finish simulation quality/material presets and consistent workbench UX.
9. Export/package/documentation and optional solver benchmark only after all release gates are green.

## Supervisor rules

- `AGENT_STATUS.md` is the coordination record.
- One canonical Actions workflow only.
- Public FreeCAD workbench commands, task panels and document objects are the acceptance surface.
- No utility-only implementation is considered complete.
- Semantic sewing references must never silently retarget after topology changes.
- Every merged functional slice needs canonical FreeCAD/Xvfb verification before being treated as release-ready.

## Current blocker

Run 33308932031 on main failed immediately with zero jobs. Issue #293 tracks this control-plane problem. PR #294 is a deliberately minimal canonical-workflow repair/probe; it retains the real FreeCAD and Xvfb paths while removing nonessential workflow complexity until scheduling is proven.

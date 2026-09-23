# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository
- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Main at replan: `dad152e634bcf454bc71aa02f4c1bfa858c154c1`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor issue: #1017.
- Active release candidate: PR #1044, branch `supervisor/release-final-20260923`.

## Evidence
- Diagnostic run #3297 / `35844023654`: Python, staged sewing, production export, basic blanket visual, README turntables and full tunic audit passed; Native Sketcher acceptance failed by timeout after its 8-minute fail-closed limit.
- Run #3297 artifacts inspected directly. The blanket artifact records opposite-corner pins, `edge_spike_ratio=2.703), finite connected mesh, drape pass, 99.148 mm material movement and a 16-frame motion GIF. Tunic, sewing, export and turntable artifacts were also inspected.
- The Sketcher timeout log showed the FreeCAD process reached the acceptance command after checkout/image startup but produced no script-stage output because the test attempted workbench activation without first ensuring `InitGui.py` had registered the workbenches.
- The release candidate fixes that boundary and also aligns the README blanket turntable with the validated blanket fixture rather than merely checking motion.

## Current gate
- Do not merge or close #1017/#1020/#1041/#1042 yet.
- Exact-head PR validation has not been exposed by the GitHub connector; branch push runs fail with zero jobs. Treat that as an external Actions orchestration blocker, not success.
- After exact-head terminal validation becomes available: merge PR #1044, verify merged-main canonical CI, reconcile `TOOL_STATE.md`, `ROADMAP.md`, open issues/PRs and stale branches, then close completed durable records with explicit reasons.

## Non-negotiables
- FreeCAD/Sketcher remains authoritative for geometry and persistence.
- Derived simulation state is rebuildable/invalidation-aware.
- No weakened mesh or screenshot thresholds.
- No second workflow.

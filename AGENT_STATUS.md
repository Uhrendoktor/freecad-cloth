# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `8cee5774c25110448675e7b45d651869f3921692`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release-closeout PR: #1066, branch `supervisor/complete-audit-20260923`, head `af1e98d12a2287e9042aebb3ef9cb163bf97354c`.

## Implemented release slice on main

- Public PatternPiece creation with native Sketcher authority is idempotent and has focused regression coverage.
- Native Sketcher acceptance bootstraps the workbench, emits stage markers, validates placed/world-space seam endpoints, deterministic seam color, save/reload authority and downstream invalidation.
- Blanket-over-Cube validation uses generic FreeCAD geometry with mesh collision, opposite top-edge corner pins, finite connected mesh/drape checks, real motion and material-presentation evidence.
- README turntable generation requires 73 distinct frames, camera checkpoint distinctness and mesh-quality evidence.
- Human-facing installation/user-guide/example documentation is present.
- Current release-closeout correction (#1066) restores the evidence-backed 200 mm blanket fixture for both basic visual validation and README turntable generation.

## CI evidence

- Supporting canonical run #35845226384 ran real FreeCAD/Xvfb jobs. The 200 mm Basic blanket visual job passed, including material presentation and 16 motion frames.
- In that supporting run, README turntable failed its drape sanity gate and Native Sketcher acceptance failed; the logs/artifacts were inspected. Later production changes addressed the fixture/runtime bugs, but no exact-head terminal-green run has yet been obtained.
- Merged-main push run #3394 and PR #1066 push run #3397 both fail before job allocation with zero jobs.
- Existing research run #3360 proved AppRun CLI/FreeCAD/GUI/Part/Sketcher imports succeed, while the full Sketcher acceptance still timed out at the unchanged 8-minute limit with an empty acceptance log.

## Current gate

- Do not close #1017 or merge #1066 until exact-head canonical validation and merged-main canonical validation are terminal-green.
- Issue #1053 remains the external Actions event-delivery blocker. The repository-side response is to preserve the single canonical workflow and leave the reproducible admin/Actions-policy restoration path documented.
- Open actionable issues currently include #1017, #1020, #1041, #1042, #1043, #1048, #1053 and #1055.

# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `dad152e634bcf454bc71aa02f4c1bfa858c154c1`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1063, branch `supervisor/root-completion-20260923`, head `e0b075508b008b19b65ebb0a8be6392e01e63b3f`.
- Validation alias: PR #1065, branch `research/root-completion-exacthead-20260923`, same head; validation alias is not mergeable separately.
- Predecessor PR #1058 was closed without merge during event-delivery validation; the production branch remains intact.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- The acceptance script was audited for executable defects; the production candidate now imports `pathlib.Path` and defines its stage-marker helper before use.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- Blanket turntable drape sanity derives target dimensions from the FreeCAD Shape bounding box, matching the actual `Part::Feature` fixture.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.
- The directly inspected stabilized blanket artifact (#10743635540) shows coherent pinned drape motion and its log reports passing mesh, drape, movement, material-presentation and motion-frame checks.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed real FreeCAD/Xvfb jobs. Python, sewing, pattern export, blanket visual, README turntable and tunic audit passed; Native Sketcher acceptance timed out after its 8-minute fail-closed limit.
- Diagnostic canonical run #3360 / `35845914342` proved the FreeCAD AppRun CLI, FreeCAD, FreeCADGui, Part, Sketcher and combined imports all terminate successfully. The full native Sketcher acceptance invocation then timed out after 8 minutes and uploaded a 162-byte artifact containing a zero-byte acceptance log.
- The exact release candidate #1063 currently has no pull_request workflow run/check. Validation PR #1065 carries the identical candidate tree and is being used only to obtain an executable pull_request run.
- Repeated main/non-main push runs can terminate with zero jobs. PR-triggered runs exist and execute on other PRs, so this is recorded as an Actions event-delivery/orchestration blocker rather than validation success.

## Current gate

- Do not merge PR #1063 or close #1017 yet.
- Exact-head PR #1063 must receive a terminal canonical run and its jobs/artifacts/logs must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- Research issue #1055 remains open because run #3360 proved all FreeCAD/GUI/Part/Sketcher imports pass but the full acceptance invocation timed out before the first acceptance log byte. A newer diagnostic head is queued for another bounded probe run.
- Agent issues #1020, #1042, #1043, #1048 remain open until their changes are present on merged main with terminal-green evidence.
- Actions orchestration issue #1053 remains open until exact candidate CI can be dispatched and observed.

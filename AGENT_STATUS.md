# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `dad152e634bcf454bc71aa02f4c1bfa858c154c1`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1063, branch `supervisor/root-completion-20260923`, head `b95bedb7e1627f178aba437cbd8c13f62842e882`.
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
- The exact release candidate #1063 currently has no pull_request workflow run/check. Validation-only PRs #1060 and #1061 reproduced the same missing-run condition and are closed.
- Repeated main/non-main push runs can terminate with zero jobs. PR-triggered runs exist and execute on other PRs, so this is recorded as an Actions event-delivery/orchestration blocker rather than validation success.

## Current gate

- Do not merge PR #1063 or close #1017 yet.
- Exact-head PR #1063 must receive a terminal canonical run and its jobs/artifacts/logs must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- Research issue #1055 remains open because the diagnostic run has isolated the problem to the full acceptance invocation but has not yet received a run for its new module-entry probe.
- Agent issues #1020, #1042, #1043, #1048 remain open until their changes are present on merged main with terminal-green evidence.
- Actions orchestration issue #1053 remains open until exact candidate CI can be dispatched and observed.

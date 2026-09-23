# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `dad152e634bcf454bc71aa02f4c1bfa858c154c1`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1058, branch `supervisor/root-completion-20260923`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed real FreeCAD/Xvfb jobs. Python, sewing, pattern export, blanket visual, README turntable and tunic audit passed; only Native Sketcher acceptance timed out after its 8-minute fail-closed limit.
- The timeout job log showed the FreeCAD process reached the test invocation but emitted no acceptance-stage output. The bounded fix in PR #1058 bootstraps the workbench registration before activation.
- Repeated non-main and main push workflow runs terminate with zero jobs. PR-triggered runs exist and execute normally on other branches, so the zero-job state is recorded as an Actions orchestration blocker rather than test success.

## Current gate

- Do not merge or close #1017 yet.
- Exact-head PR #1058 must receive a terminal canonical run and its jobs/artifacts/logs must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- Stale/overlapping PRs are being closed; only targeted research #1057 remains active while its evidence is useful.


# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `379a89fca4d331e985ddec88987217c0bde920ef`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1066, branch `supervisor/complete-audit-20260923`, live head `7141ed6a8c9e49dd3e85c171401aeebf28ff17c6`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed real FreeCAD/Xvfb jobs. Python, sewing, pattern export, blanket visual, README turntable and tunic audit passed; only Native Sketcher acceptance timed out after its 8-minute fail-closed limit. The 200 mm Blanket-over-Cube fixture was separately validated in real FreeCAD/Xvfb by run `35845226384`, artifact `10743635540`.
- The timeout job log showed the FreeCAD process reached the test invocation but emitted no acceptance-stage output. The merged release now explicitly bootstraps workbench registration before activation and includes flushed acceptance stage markers.
- Repeated non-main and main push workflow runs terminate with zero jobs. PR-triggered runs exist and execute normally on other branches, so the zero-job state is recorded as an Actions orchestration blocker rather than test success. Current main push run `35847413862` is one such zero-job failure.

## Branch cleanup

- Many historical agent/supervisor branches remain. The installed GitHub connector exposes branch listing but no branch-delete operation, so branch cleanup is not claimed complete.

## External CI blocker

- GitHub Actions event delivery remains unresolved: main/non-main push runs can terminate `failure` with zero jobs, while historical pull_request/schedule runs instantiate the canonical job graph.
- Repository-side policy inspection requires Administration access not exposed by the installed GitHub connector. Exact restoration path is recorded in issue #1053: inspect inherited/repository Actions event restrictions, then trigger a real `pull_request:synchronize` on PR #1066 and verify non-zero jobs.

## Current gate

- Do not merge or close #1017 or continuation #1067 yet.
- Exact-head PR #1066 must receive a terminal canonical run and its jobs/artifacts/logs must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- Stale/overlapping PRs have been superseded. PR #1066 is the sole open release PR; #1053 and #1055 document external Actions/Sketcher evidence.


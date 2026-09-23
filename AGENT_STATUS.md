# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `707eb8dfc01c8d834daba4bb87c79c597b889cc5` at this audit; resolve `refs/heads/main` again before future mutations.
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1075, branch `supervisor/final-release-fixed-main-20260923`; exact head `d346200094d323e3f55cab1832a7b2343aa7ee7e`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed real FreeCAD/Xvfb jobs. Python, sewing, pattern export, blanket visual, README turntable and tunic audit passed; only Native Sketcher acceptance timed out after its 8-minute fail-closed limit. The 200 mm Blanket-over-Cube fixture was separately validated in real FreeCAD/Xvfb by run `35845226384`, artifact `10743635540`.
- The timeout job log showed the FreeCAD process reached the test invocation but emitted no acceptance-stage output. Main now also includes the reviewed module-level `run_acceptance()` launcher fix from merged PR #1074, matching FreeCAD's documented/import behavior; runtime confirmation remains blocked by Actions delivery.
- Current PR #1075 has no `pull_request` workflow run or status. Exact-head push run #3492 / `35867820895` terminates `failure` before job allocation with zero jobs and zero artifacts. A controlled close/reopen probe on PR #1075 at the prior frozen head produced no `pull_request` workflow run; the current frozen head is now d346200094d323e3f55cab1832a7b2343aa7ee7e.
- Other branches still have real `pull_request` runs, and historical scheduled execution proves the canonical workflow graph can run when GitHub delivers the event. The installed connector cannot read the Actions administration policy endpoints (403/unsupported integration access) and exposes no workflow-dispatch operation; scheduled execution has historical success but current event delivery for pushes/pull requests is still blocked.

## Branch cleanup

- 490 historical agent/supervisor and other branches remain. The installed GitHub connector exposes branch listing but no branch-delete operation, so branch cleanup is not claimed complete.

## External CI blocker

- GitHub Actions event delivery remains unresolved: current main/release push runs can terminate `failure` with zero jobs, while other historical pull_request/schedule runs instantiate the canonical job graph.
- Repository-side policy inspection requires Administration access not exposed by the installed GitHub connector. Exact restoration path is recorded in issue #1053: inspect inherited/repository Actions event restrictions, then trigger a real `pull_request:synchronize` or `reopened` event on PR #1075 and verify non-zero jobs.

## Current gate

- Do not merge or close #1017 or continuation #1067 yet.
- Exact-head PR #1075 must receive a terminal canonical run and its jobs/artifacts/logs must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- PR #1073 has been superseded and closed; PR #1074 and #1077 have been merged; PR #1075 is the sole open release PR; validation PR #1078 was opened against the identical candidate SHA to probe event delivery and then closed without a run; continuation #1079 is the current depth-2 supervisor continuation; #1053 is the active external CI blocker; #1020 and #1043 remain open until their acceptance gates are verified on merged main.

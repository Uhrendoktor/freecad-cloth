# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `ccac198eae37bb162830895b1d8259ca84d7047f`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1066, branch `supervisor/complete-audit-20260923`, live head `2dbdd237742f518befbe50a3cfa4521c16abbaca`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the validated 200 mm blanket fixture, pins derived from the same fixture dimension, and the canonical pinned Tissu mesh-collision runtime.
- Installation/docs index points users to the human-facing User Guide.

## CI evidence

- Supporting run `35845226384` executed real FreeCAD/Xvfb jobs. The Basic Blanket-over-Cube job passed and produced artifact `10743635540`; its log reports a finite connected 4429-vertex mesh, spike ratio 2.337, footprint aspect 1.205, 106.373 mm motion, material-presentation acceptance, and 16 motion frames.
- In that same run, the older README turntable source failed its fail-closed drape sanity gate with a detached-candidate state. That source used a 20 mm particle-distance / 32-iteration CPU configuration and is not the current release head.
- The current release branch now uses the 200 mm fixture and the canonical Tissu backend for the README turntable, with no relaxation of drape, motion, mesh, frame-count, timeout, or artifact assertions.
- Exact-head PR #1066 currently has no commit status and no pull_request workflow run. Controlled close/reopen produced no run; validation PR #1070 pointed at the same exact head and also produced no pull_request run before being closed.
- Recent candidate push runs #3445 / Actions 35856692674 and #3444 / Actions 35856533198 failed before job allocation with zero jobs/artifacts. Retrying `35855453586` through the connector returned GitHub 403: `This workflow run cannot be retried`.

## Branch cleanup

- Many historical agent/supervisor/validation branches remain: 484 remote branches are currently present. The installed GitHub connector exposes branch listing but no branch-delete operation, so branch cleanup is not claimed complete.

## External CI blocker

- GitHub Actions event delivery remains unresolved: recent push runs terminate with failure and zero jobs, while historical pull_request/schedule runs instantiate the canonical job graph.
- Repository ruleset inspection is available and reports no repository rulesets; branch-protection/Actions administration endpoints return integration-access denial, so inherited repository/org event policy cannot be inspected or changed through the installed connector.
- Exact restoration path is recorded in issue #1053: an authorized repository/org administrator must inspect Actions event restrictions, ensure `pull_request` delivery is allowed, trigger a real `pull_request:synchronize` or `reopened` event for PR #1066, then inspect all canonical jobs/logs/artifacts.

## Current gate

- Do not merge or close #1017 or continuation #1067 yet.
- Exact-head PR #1066 must receive a terminal canonical run and its jobs/artifacts/logs must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- PR #1069 is closed as a superseded duplicate. PR #1070 was a validation-only exact-head probe and is closed. PR #1066 is the sole open release PR.

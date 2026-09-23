# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `ccac198eae37bb162830895b1d8259ca84d7047f`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1066, branch `supervisor/complete-audit-20260923`, code head `28b8b251ccb6991466ab7e8657d9397419f2c706`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed the real FreeCAD/Xvfb release graph; all release jobs passed except the then-unfixed Native Sketcher acceptance timeout.
- Supporting run #3331 / Actions `35845226384` validated the 200 mm × 200 mm Blanket-over-Cube fixture in real FreeCAD/Xvfb, artifact `10743635540`, with unchanged fail-closed mesh/drape/motion/material checks.
- Current main push run #3412 / Actions `35848880387` terminates immediately with `failure` and zero jobs. The prior reconciled PR-head push run #3413 / Actions `35849087425` also failed with zero jobs/artifacts; after rebuilding the branch from live `main`, code commits `997e1f7b915bbcedda874f08aabbfe068653082a` and `28b8b251ccb6991466ab7e8657d9397419f2c706` received no workflow run or status. PR #1066 still has no `pull_request` run/check.

## Branch cleanup

- Many historical agent/supervisor branches remain. The installed GitHub connector exposes branch listing but no branch-delete operation, so branch cleanup is not claimed complete.

## External CI blocker

- GitHub Actions event delivery remains unresolved: current push runs terminate `failure` with zero jobs, while historical `pull_request` and `schedule` runs instantiate the canonical job graph.
- The rulesets endpoint currently returns `[]`, but the connector does not expose the repository Actions policy endpoints needed to inspect inherited `restrict_action_events` settings. The exact restoration path is recorded in issue #1053: inspect repository/inherited Actions event policy, then trigger a real `pull_request:synchronize`/reopen for #1066 and verify a non-zero canonical job graph.

## Current gate

- Do not merge or close #1017 or continuation #1067 yet.
- Exact-head PR #1066 code head is `28b8b251ccb6991466ab7e8657d9397419f2c706`; it must receive a real `pull_request` canonical run that is terminal-green, with jobs/logs/artifacts inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- Stale/overlapping PRs have been superseded. PR #1066 is the sole open release PR; #1053 documents the external Actions blocker and #1055 records the completed Sketcher diagnosis.


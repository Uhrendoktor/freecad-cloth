# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `b99e8dbdfc2b91c8da645c4b41bf22ff4aa0cec6` (resolved at supervisor audit time).
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation: #1081.
- Active release candidate: PR #1075, branch `supervisor/final-release-fixed-main-20260923`; exact head `69215e7286ffda3da655f53094c5ae86d4644eb3`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.
- PR #1074 launcher fix and PR #1077 missing icon fix are merged on main.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed real FreeCAD/Xvfb jobs. Python, sewing, pattern export, basic blanket, README turntable and tunic audit passed; Native Sketcher acceptance timed out after its 8-minute fail-closed limit. The 200 mm Blanket-over-Cube fixture was separately validated in real FreeCAD/Xvfb by run `35845226384`, artifact `10743635540`; its rendered checkpoints and motion frames were visually inspected.
- Current PR #1075 exact head `69215e7…` has no pull_request workflow run and no commit status. Its latest push-triggered run is #3507 / Actions `35879364633`, terminal `failure` before job allocation with 0 jobs and 0 artifacts. Predecessor candidate pushes #3505/#3506 and current-main pushes #3499/#3504 show the same pre-job zero-job failure pattern.
- A controlled PR close/reopen probe was previously performed and did not create a pull_request run. The installed GitHub connector exposes no workflow-dispatch operation and cannot read the required Actions administration policy endpoints.
- The exact-head release decision must therefore treat canonical validation as unverified until a real non-zero job graph runs at `69215e7286ffda3da655f53094c5ae86d4644eb3`.
- The supporting 200 mm Blanket artifact is valid evidence for the basic example only; it does not substitute for exact-head README turntable validation.

## Branch cleanup

- 490 historical agent/supervisor and other branches were observed in the current audit chain. The installed GitHub connector exposes branch listing but no branch-delete operation, so branch cleanup is not claimed complete.

## Current gate

- Do not merge or close #1017 or continuation #1081.
- Exact-head PR #1075 must receive a terminal canonical run with non-zero jobs, and every required job, log and artifact must be inspected.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- #1020 and #1043 remain open until their stated acceptance gates are verified on merged main.
- #1053 remains the active external CI blocker.
- #1083 is the independent challenge review for the release-blocker/evidence boundary.
- Stale state in this file has been reconciled to the live main/PR heads as part of the 2026-09-23 recovery audit.

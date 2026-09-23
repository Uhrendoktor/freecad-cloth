# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `8ad49c8197d173c2279d3d955cf7af5084780567` (resolved at audit time).
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation: #1094.
- Active release candidate: PR #1075, branch `supervisor/final-release-fixed-main-20260923`; exact frozen head `69215e7286ffda3da655f53094c5ae86d4644eb3`.
- Timing-fix PR: #1090, branch `supervisor/readme-gif-delay-fix-20260923`; head `76a37cc9e78a1d810f9c6c116c0d20b14a00124e`.
- Current candidate relation to main: exact release SHA is 2 commits ahead / 5 behind main; the behind side is subsequent supervisor/documentation history. Do not rebase/synchronize the frozen release SHA.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.
- PR #1074 launcher fix and PR #1077 missing icon fix are merged on main.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed the real 12-job graph. Python, sewing, pattern export, basic blanket and tunic audit passed; Native Sketcher acceptance failed; publication and benchmark jobs were skipped according to their conditions.
- Supporting real FreeCAD/Xvfb run #3331 / `35845226384`, artifact `10743635540`, validates the 200 mm Blanket-over-Cube fixture. The artifact contains 16 distinct 640x480 motion frames and representative checkpoints were visually inspected; it is supporting evidence, not exact-head README-turntable proof.
- PR #1075 is open at exact head `69215e7286ffda3da655f53094c5ae86d4644eb3`. The latest exact-head push run #3556 / `35904941979` failed before job allocation with 0 jobs and 0 artifacts. No exact-head `pull_request` run/status is present.
- Timing-fix PR #1090 is intentionally separate and also has no `pull_request` workflow run/status.
- Current main push runs also continue to fail before job allocation with zero jobs/artifacts, indicating the blocker remains upstream of repository test jobs.
- The canonical workflow topology and fail-closed assertions have not been weakened.
- No true 03:00 UTC retention execution is evidenced today; the last evidenced scheduled run was #3225 / `35839191664`, whose retention job was skipped because that run used the 5-minute schedule.

## User-facing assets

- `docs/screenshots` is still missing `docs/images/generated/cloth-blanket-motion.gif` even though README references it.
- Artifact `10743635540` contains the genuine `blanket-motion.gif` plus 16 motion-frame PNGs. The GIF is 16-frame 640x480 motion media, but its frame timing is 0 ms; the corrected timing is owned by PR #1090 and browser playback timing remains a required gate.
- The canonical workflow is already the authoritative publisher; do not publish a fabricated/static substitute.

## Repository hygiene

- Fresh branch pagination currently observes 498 remote branches.
- The installed GitHub connector exposes branch listing but no branch-delete operation; branch cleanup is therefore not claimed complete.
- TODO/FIXME/XXX repository searches on current main returned no matches.
- Release-replacement PRs #1093, #1095 and #1096 were closed unmerged so #1075 remains the sole release path.

## Current gate

- Do not merge or close #1017 or #1094.
- Do not merge #1075 or #1090 until their respective canonical validation gates are terminal-green.
- Exact-head #1075 must receive a non-zero canonical job graph; inspect every required job, step/log and artifact before merge.
- After merge, merged-main canonical validation must be terminal-green before supervisor closure.
- #1020 and #1043 remain open until their stated acceptance gates are verified against merged-main evidence.
- #1053 remains the external Actions control-plane/event-execution blocker.
- #1084 remains bounded to genuine README GIF publication and browser playback validation.
- Stale state in this file was reconciled from live GitHub evidence in the 2026-09-23 depth-7 audit.

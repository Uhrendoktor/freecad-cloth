# Agent status

Machine-readable supervisor/release record. Durable guidance lives in docs/DEVELOPMENT.md.

## Repository

- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Current main at this reconciliation: ec9b8d9a868cb3ed8e566f237cb521067d8ad703.
- Canonical workflow: .github/workflows/canonical-execution.yml; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation ledger: #1098; root #1017 remains active.
- Active release candidate: PR #1075, branch supervisor/final-release-fixed-main-20260923; live head 077afd75579f79410279714ebc285f2e0561956d.
- Timing-fix PR: #1090, branch supervisor/readme-gif-delay-fix-20260923; head a5cb1a82cba839a853c37bd4abeda5e91937a860.
- Candidate relation at audit time: 3 commits ahead / 17 behind main. The behind side is later supervisor/documentation history. Do not rebase merely to remove the behind count; validate the actual live PR head.

## Implemented release slice

- Native CreatePieceWithSketch is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps InitGui.py, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.
- PR #1074 launcher fix and PR #1077 missing icon fix are merged on main.

## CI evidence

- Supporting canonical run #3297 / 35844023654 executed the real 12-job graph. Python, sewing, pattern export, basic blanket and tunic audit passed; Native Sketcher acceptance failed; publication and benchmark jobs were skipped according to their conditions.
- Supporting real FreeCAD/Xvfb run #3331 / 35845226384, artifact 10743635540, validates the 200 mm Blanket-over-Cube fixture. The artifact contains 16 distinct 640x480 motion frames and representative checkpoints were visually inspected; it is supporting evidence, not exact-head README-turntable proof.
- Live release PR #1075 is at 1433f343089dc794e297c1c5fa27094dc1333c07. Latest live-head push run #3594 / 35906114777 failed before job allocation with 0 jobs and 0 artifacts; current-head check-runs are empty and no pull_request job graph/status was delivered.
- Timing PR #1090 is at a5cb1a82cba839a853c37bd4abeda5e91937a860 and has no pull_request workflow run/status.
- Current main push runs continue to fail before job allocation with zero jobs/artifacts, indicating the blocker remains upstream of repository test jobs.
- The canonical workflow topology and fail-closed assertions have not been weakened.
- No true 03:00 UTC retention execution is evidenced today; the last evidenced scheduled run was #3225 / 35839191664, whose retention job was skipped because that run used the 5-minute schedule.

## User-facing assets

- docs/screenshots is still missing docs/images/generated/cloth-blanket-motion.gif even though README references it.
- Artifact 10743635540 contains the genuine blanket-motion.gif plus 16 motion-frame PNGs. The GIF is 16-frame 640x480 motion media, but its frame timing is 0 ms; #1090 owns the bounded timing correction and browser playback timing remains a required gate.
- The canonical workflow is already the authoritative publisher; do not publish a fabricated/static substitute.
- Supporting rendered checkpoints from artifact 10743635540 were visually inspected in this recovery and show coherent arranged/intermediate/draped cloth over the cube.

## Repository hygiene

- Fresh branch pagination currently observes 501 remote branches.
- The installed GitHub connector exposes branch listing but no branch-delete operation; branch cleanup is therefore not claimed complete.
- TODO/FIXME/XXX repository searches on current main returned no matches.
- Release duplicate PRs #1093, #1095 and #1096 are closed unmerged; #1075 remains the sole geometry release path.
- Timing PR #1090 is the active timing path; earlier timing duplicates were retired.
- #1099 is closed after its bounded static-contract scope was implemented on the release branch.

## Current gate

- Do not merge or close #1017 or #1098.
- Do not merge #1075 or #1090 until their respective canonical validation gates are terminal-green.
- Exact-head #1075 must receive a non-zero canonical job graph; inspect every required job, step/log and artifact before merge.
- After merge, merged-main canonical validation must be terminal-green before supervisor closure.
- #1020 and #1043 remain open until their stated acceptance gates are verified against merged-main evidence.
- #1053 remains the external Actions control-plane/event-execution blocker.
- #1084 remains bounded to genuine README GIF publication and browser playback validation.
- This record reflects live GitHub evidence at reconciliation time; it is not a frozen release pointer.
- #1105 is the single active researcher stream for the FreeCAD 1.1 workbench activation/startup boundary; duplicate #1106 is closed.
- #1107 is research-only instrumentation and remains unverified because target push events still fail before job allocation.


## Recovery reconciliation — 2026-09-23 21:30 CEST

- main = ec9b8d9a868cb3ed8e566f237cb521067d8ad703; the temporary unvalidated Sketcher launcher change was reverted.
- #1075 remains the geometry release PR at 077afd75579f79410279714ebc285f2e0561956d; #1090 remains the independent GIF timing PR at a5cb1a82cba839a853c37bd4abeda5e91937a860.
- #1105 is the single active FreeCAD startup/import-boundary researcher issue. #1108 is closed as superseded. PRs #1109 and #1110 are closed after the bounded GUI-order/tmp bootstrap hypothesis was falsified by pinned FreeCAD fallback evidence; no production InitGui change was made.
- Fallback run #618 / workspace run 35908076546 exercised the repaired acceptance path against the pinned FreeCAD 1.1.0 image and timed out at the unchanged 8-minute Native Sketcher gate (exit 124). The candidate acceptance source was identical at the repaired and current #1109 heads, so the proposed startup-order repair is not sufficient.
- Current target canonical push runs for main, #1075, and #1090 still terminate before job allocation with zero jobs. No exact-head pull_request graph exists for the release gate.
- The README blanket GIF remains unpublished on docs/screenshots. Supporting artifact 10743635540 remains valid real FreeCAD evidence: 16 distinct 640x480 motion frames and coherent rendered checkpoints; #1090 owns the 100 ms timing correction.
- No release merge or supervisor closure is authorized until #1053 is externally restored, #1105 yields a distinct runtime fix with exact-head evidence, #1075/#1090 pass their required gates, the genuine GIF is published/browser-validated, and merged-main validation is green.

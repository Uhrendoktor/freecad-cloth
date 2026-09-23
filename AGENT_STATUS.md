# Agent status

Machine-readable supervisor/release record. Durable guidance lives in docs/DEVELOPMENT.md.

## Repository

- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Current main at this reconciliation: a5f4892b2347aeec3492e21e016ccda85f9c92ab.
- Canonical workflow: .github/workflows/canonical-execution.yml; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation ledger: #1098; root #1017 remains active.
- Active release candidate: PR #1075, branch supervisor/final-release-fixed-main-20260923; live head 1433f343089dc794e297c1c5fa27094dc1333c07.
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

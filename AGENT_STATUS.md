# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `8ad49c8197d173c2279d3d955cf7af5084780567` (resolved at audit time).
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation: #1094.
- Timing-fix child PR: #1092, branch `agent/fix-blanket-gif-delay-20260923`; head `e92d796bcd8bada1b7c27e887121ad1f16049cac`..
- Active release candidate: PR #1093, branch `supervisor/release-candidate-69215e7-recovery-20260923`; exact head `69215e7286ffda3da655f53094c5ae86d4644eb3`..
- Current candidate relation to main: exact release SHA is 2 commits ahead / 5 behind main; the behind side is subsequent supervisor/documentation history. Do not rebase/synchronize the frozen release SHA.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.
- PR #1074 launcher fix and PR #1077 missing icon fix are merged on main.

## CI evidence

- Supporting canonical run #3297 / `35844023654` executed real FreeCAD/Xvfb jobs. Python, sewing, pattern export, basic blanket, README turntable and tunic audit passed; Native Sketcher acceptance timed out after its 8-minute fail-closed limit.
- Supporting real FreeCAD/Xvfb run #3331 / `35845226384`, artifact `10743635540`, validates the 200 mm Blanket-over-Cube fixture. The artifact contains 16 distinct motion frames and was visually inspected; it is supporting evidence for the basic example only, not exact-head README-turntable proof.
- Current PR #1093 exact head `69215e7…` has no pull_request workflow run or commit status; exact-head fetch returns no PR-triggered run.
- Timing-fix PR #1090 exact head `76a37cc…` also has no pull_request workflow run or commit status.
- Fresh main state-sync pushes #3508 / `35902921024`, #3509 / `35903456264`, #3510 / `35903560622`, and #3537 / `35904391656` also failed before job allocation with 0 jobs and 0 artifacts.
- Historical scheduled run #3225 / `35839191664` succeeded and instantiated 12 jobs, but its retention-cleanup job was skipped because the run used the 5-minute schedule. No later daily 03:00 UTC retention run is currently evidenced.
- An independent challenge review on PR #1075 and researcher issue #1083 both identify the strongest alternative as an Actions control-plane/policy problem rather than a job-level repository defect. The falsifier is a real exact-head run with a non-zero job graph or control-plane metadata showing a later-stage failure. No validation gate was weakened.

## User-facing assets

- The stable `docs/screenshots` branch is missing `docs/images/generated/cloth-blanket-motion.gif` even though README references it.
- The canonical publisher job is already the intended source: it copies the genuine 16-frame blanket motion GIF from the validated blanket artifact into that exact path after a successful main push.
- Issue #1084 is the active bounded asset-publication issue. Duplicate issue #1085 was closed as duplicate.
- Freshly downloaded supporting artifact #10743635540 contains 16 genuine 640x480 motion PNGs with 16 distinct hashes; its existing GIF reports 0 ms per-frame delay. A corrected local encode of those genuine frames with `-delay 10` before the input glob reports 16 frames at 100 ms each. Final published-asset validation therefore must include usable browser playback timing rather than treating multi-frame validity alone as complete.
- Historical README turntable artifact inspection showed the old draped blanket geometry had severe high-frequency triangular spikes; this materially supports keeping exact-head README turntable execution as a release falsifier.

## Repository hygiene

- Fresh REST pagination observes 497 remote branches. Older continuation notes claiming 487/490/491 from partial inventories are not substitutes for this current full count.
- The installed GitHub connector exposes branch listing but no branch-delete operation, so source-side branch deletion is not claimed complete.
- Dependabot, contribution/security/CoC files, issue templates, installation docs, user guide, development guide, roadmap and release gates are present.
- TODO/FIXME repository searches returned no matches.

## Current gate

- Do not merge or close #1017 or active continuation #1094.
- Do not merge #1093 or #1090 until the relevant canonical validation gates become terminal-green.
- Exact-head PR #1093 must receive a terminal canonical run with non-zero jobs; inspect every required job, step/log and artifact.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- #1020 and #1043 remain open until their stated acceptance gates are verified on merged main.
- #1053 remains the external Actions control-plane/event-execution blocker and carries current head/run/branch-count evidence.
- #1083 is the completed independent challenge child; #1084 owns README GIF publication; #1090 owns the isolated GIF timing fix. Duplicate timing PRs #1091 and #1092 are closed unmerged.
- Stale state in this file was refreshed from live GitHub state in the 2026-09-23 recovery audit.

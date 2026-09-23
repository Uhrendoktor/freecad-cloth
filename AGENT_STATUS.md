# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `86c048039812dd0e4bb0541547cc0e610c72b135` (resolved at audit time).
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation: #1086.
- Active release candidate: PR #1075, branch `supervisor/final-release-fixed-main-20260923`; exact head `69215e7286ffda3da655f53094c5ae86d4644eb3`.

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
- Current PR #1075 exact head `69215e7…` has no pull_request workflow run or commit status. Latest exact-head push run #3507 / `35879364633` failed before job allocation with 0 jobs and 0 artifacts.
- A fresh main push produced by state reconciliation, run #3508 / `35902921024`, also failed before job allocation with 0 jobs and 0 artifacts.
- Historical scheduled run #3225 / `35839191664` succeeded and instantiated 12 jobs, but its retention-cleanup job was skipped because the run used the 5-minute schedule. No daily 03:00 UTC retention run is currently evidenced.
- An independent challenge review on PR #1075 recorded the strongest alternative (repository/workflow defect) and the falsifier (a real non-zero exact-head job graph). No validation gate was weakened.

## User-facing assets

- The stable `docs/screenshots` branch is missing `docs/images/generated/cloth-blanket-motion.gif` even though README references it.
- The canonical publisher job is already the intended source: it copies the genuine 16-frame blanket motion GIF from the validated blanket artifact into that exact path after a successful main push.
- Issue #1084 is the active bounded asset-publication issue. Duplicate issue #1085 was closed as duplicate.
- The downloaded supporting GIF has genuine motion but was observed with 0 ms per-frame GIF delay metadata, so final published asset validation must include usable browser playback timing rather than treating mere multi-frame validity as complete.

## Repository hygiene

- Fresh branch pagination observes 391 remote branches. Older continuation notes claiming 490 are stale.
- The installed GitHub connector exposes branch listing but no branch-delete operation, so source-side branch deletion is not claimed complete.
- Dependabot, contribution/security/CoC files, issue templates, installation docs, user guide, development guide, roadmap and release gates are present.
- TODO/FIXME repository searches returned no matches.

## Current gate

- Do not merge or close #1017 or #1086.
- Exact-head PR #1075 must receive a terminal canonical run with non-zero jobs; inspect every required job, step/log and artifact.
- After merge, merged-main canonical validation must be terminal-green before closing supervisor issues.
- #1020 and #1043 remain open until their stated acceptance gates are verified on merged main.
- #1053 remains the external Actions delivery/control-plane blocker and now has current head/run/branch-count evidence.
- #1083 is the independent challenge child; #1084 owns the README GIF publication.
- Stale state in this file was refreshed from live GitHub state in the 2026-09-23 recovery audit.

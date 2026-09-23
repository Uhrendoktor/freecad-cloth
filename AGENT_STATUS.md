# Agent status

Machine-readable supervisor/release record. Durable guidance lives in docs/DEVELOPMENT.md.

## Repository

- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Last audited main tip: dd4453cdc578f755fbed1d7dc68c3f1d2d6f31af.
- Canonical workflow: .github/workflows/canonical-execution.yml; exactly one workflow.
- Supervisor completion issue: #1017.
- Current continuation: #1094.
- Active geometry release candidate: PR #1096, branch supervisor/final-release-fixed-main-20260923; exact code head 69215e7286ffda3da655f53094c5ae86d4644eb3.
- Independent timing fix: PR #1090, branch supervisor/readme-gif-delay-fix-20260923; head 76a37cc9e78a1d810f9c6c116c0d20b14a00124e.

## Implemented release slice

- Native CreatePieceWithSketch is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance bootstraps InitGui.py, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and existing fail-closed mesh thresholds.
- README turntable uses the same 200 mm blanket fixture, pinned Tissu mesh-collision runtime, finite/connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.
- PR #1074 launcher fix and PR #1077 missing icon fix are merged on main.

## CI evidence

- Supporting canonical run #3297 / 35844023654 executed real FreeCAD/Xvfb jobs; Python, sewing, pattern export, basic blanket, README turntable and tunic audit passed, while Native Sketcher acceptance timed out under its fail-closed limit.
- Supporting real FreeCAD/Xvfb run #3331 / 35845226384, artifact 10743635540, validates the 200 mm Blanket-over-Cube fixture. The artifact contains 16 distinct motion frames and was visually inspected; it does not validate the exact-head README turntable.
- Exact release code head 69215e7286ffda3da655f53094c5ae86d4644eb3 has no commit statuses and no visible pull_request workflow run. Prior exact-head push run #3507 / 35879364633 and subsequent supervisor state-sync runs failed before job allocation with 0 jobs and 0 artifacts.
- Opening PR #1096 at the same exact code head has not produced a visible canonical pull_request run/check through the connector.
- PR #1090 also has no visible pull_request workflow run or commit status.
- Historical scheduled run #3225 / 35839191664 instantiated 12 jobs; the daily retention job was skipped because that run used the 5-minute schedule. No later 03:00 UTC retention execution is evidenced.
- Research issue #1053 and challenge issue #1083 identify the strongest current alternative as an Actions control-plane/event-delivery problem rather than a repository job failure. The falsifier is a delivered exact-head run with a non-zero job graph or authoritative later-stage failure metadata.

## User-facing assets

- The stable docs/screenshots branch is missing docs/images/generated/cloth-blanket-motion.gif even though README references it.
- The canonical publisher is already the intended source: it copies the genuine blanket motion GIF from the validated artifact after a successful main push.
- The supporting blanket GIF has genuine motion, but recorded frame-delay metadata was 0 ms; corrected local encoding yields 10 centiseconds per frame. Final publication still requires usable browser playback timing.
- #1084 is the bounded publication issue; do not substitute a static or fabricated asset.

## Repository hygiene

- Current branch pagination observes 497 remote branches.
- The installed GitHub connector exposes branch listing but no branch-delete operation, so source-side branch deletion is not claimed complete.
- Dependabot, contribution/security/CoC files, issue templates, installation docs, user guide, development guide, roadmap and release gates are present.
- TODO/FIXME/XXX searches returned no matches.

## Current gate

- Keep #1017 and #1094 open while release work is nonterminal.
- PR #1096 is the sole geometry release path. Do not merge it until exact-head canonical validation is terminal-green with non-zero jobs and inspected logs/artifacts.
- PR #1090 remains separate and must receive its own terminal canonical validation before merge.
- After the release merge, require fresh terminal-green canonical validation on merged main and inspect the complete job/artifact set.
- #1020 and #1043 remain open until their explicit acceptance gates are verified on merged main.
- #1053 remains the external Actions control-plane/event-execution blocker.
- #1084 remains open until the genuine README blanket GIF is published and browser-validated.
- #1088 remains open until the timing fix is canonically validated.
- Duplicate recovery PRs #1093 and #1095 are closed; obsolete supervisor continuations #1086 and #1087 are closed.
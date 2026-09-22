# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `03273ddf34e9658a91111e4f6bd575664367b37f`.
- Main's latest merge is PR #732: native Fabric-aware garment hierarchy, merged as `03273ddf34e9658a91111e4f6bd575664367b37f`.
- Main also contains the pinned-stitch fail-closed guard from merged PR #687 at its prior head `27465a33c8765c8572362eeccadc379c5c86ac5c`.
- #472 is closed; its M0 visual-trust work is complete as currently defined.
- Canonical CI: `.github/workflows/canonical-execution.yml`. Exactly one workflow exists under `.github/workflows/`.
- CI policy: preserve the Docker/Xvfb FreeCAD path and do not add a second workflow.

## Canonical workflow contract

- Triggers: `push`, `pull_request`, `workflow_dispatch`.
- Jobs: Python and FreeCAD non-GUI tests; Sewing staged creation smoke; Pattern production export smoke; Full tunic visual and simulation audit; README turntables; Publish README turntables; Measured FreeCAD workbench benchmark.
- Workflow blob: `ad6c8789d91ce3ca34825f055087e75b976647b4`.
- FreeCAD image: `ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3`.
- Preserve the existing Docker/Xvfb PNG/screenshot path, single tunic visual audit, turntable generation/publication, and one-workflow policy.

## Current PR / release state

- Open PRs at this audit: #659, #695, #702, #706, #726, #727, #728, #731, #734, #735, #738, #739, #740, #741, #743, #744, #745, #746, #747, #749, #750, #751, #752.
- Current-main release candidates include #746/#731 for sewing, #747 for PatternIR simulation boundary, #749/#751/#752 for bounded tunic validation, and #750/#726 for garment acceptance. These candidates are based on current main `03273ddf34e9658a91111e4f6bd575664367b37f`.
- #695 remains open but is based on stale main `cc93d0f8cd9451cc96667de5584cecf38c7a6350`; head `24f679a4da04a027283b6fcbf6d12d9aa85830b0`.
- #702 remains open but is stale against `cc93d0f8cd9451cc96667de5584cecf38c7a6350`; head `cae26e6c48e8b3e8f63acea3db17161390beaca8`.
- #728 remains open but is stale on `5acc453e12e1462481b85df49ba16a9c31483ee1`; it replaces the earlier #702 snapshot and needs reconciliation against current main.
- #701 is closed without merge; its hierarchy implementation is historical. The hierarchy release work actually on main is PR #732.
- #708 is closed without merge; its canonical garment-E2E workflow addition is historical and is not in the current workflow.
- #732 is merged and is the current native garment-hierarchy mainline.
- #713 is closed without merge; the pinned-stitch guard later merged through PR #687. Do not treat #713 as active implementation.
- #730 is this issue's documentation candidate and must remain based on current main before merge.

## CI evidence

- Latest exact-current-main workflow: run #2584 / run ID `35783458955` on `03273ddf34e9658a91111e4f6bd575664367b37f`; it ended `cancelled` while main was advancing. Do not treat it as terminal-green.
- Latest verified job-level evidence immediately before #732 merged: run #2560 / run ID `35783007599` on head `cc93d0f8cd9451cc96667de5584cecf38c7a6350`. Pattern export, Python/non-GUI, benchmark, sewing creation and README turntables completed successfully; the tunic job was cancelled in the main attempt but its exact-head job rerun completed successfully with job ID `106933253526`.
- Verified artifacts from that exact `cc93...` evidence: pattern-production-export `10719155792`; sewing-creation-smoke `10718832779`; tunic-visual-audit `10719056530`; readme-turntables `10719560452`; workbench-benchmark `10718268347`.
- Latest complete terminal-green canonical run remains historical run #2520 / `35782037267` on `5acc453e12e1462481b85df49ba16a9c31483ee1`; it is superseded by later main merges.
- Do not describe runs #2554, #2560, or #2584 as whole-workflow terminal-green success; record only directly verified successful jobs/artifacts.

## Architecture / durable rules

- Package root: `freecad_cloth/`; domain packages `avatar`, `pattern`, `sewing`, `simulation`; shared packages `common`, `shared`.
- Root Python files are limited to `Init.py`, `InitGui.py`, `sitecustomize.py`.
- Root domain implementations and compatibility shims are forbidden.
- FreeCAD owns editable geometry/persistence; Cloth owns garment semantics; solver owns physics.
- `PatternIR`, `SewingGraph`, `SimulationScene`, `DrapeTarget` remain semantic boundaries.
- `trimesh` stays optional/lazy; CPU reference remains correctness baseline; Tissu remains sandbox-only pending evidence.

## Outstanding gates / next focus

- Obtain a fresh terminal-green canonical validation for current main after the #732 merge; do not use cancelled workflow runs as whole-run success.
- Reconcile duplicate PatternIR slices (#747 versus #695/#744/#745) and merge only one validated current-main implementation.
- Reconcile duplicate sewing slices (#746/#731 versus #702/#728) and keep one current-main release candidate.
- Reconcile garment-acceptance candidates (#750/#726/#659/#706); retain exactly one canonical E2E path in the existing workflow.
- Keep tunic A/B branches (#749/#751/#752 and related #734/#735/#738/#740) diagnostic and single-variable; do not convert diagnostics into arbitrary hard thresholds.
- Close or explicitly supersede stale-base candidates only after evidence and state reasons are recorded.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. Never weaken tests or multiply workflows. Close issues only with an explicit state reason and a reason recorded in the durable task record.

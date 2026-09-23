# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main state: final closeout on `main`; release implementation validation is terminal-green in run #3092, and the final documentation-only validation is terminal-green in run #3094.
- Merged release PR #1001 provides the canonical garment E2E gate. Its validated source head was `40140b3a06549249c567feeb5e74dd5b766f551b`, exact-head canonical run #3076 / `35813109107`, terminal conclusion `success`.
- PR #904 was subsequently merged into main as `4e119229cd4df00b529d002dd32106b09504992e` and establishes the current canonical local-Docker-runner preference with GitHub-hosted fallback. Runs #3084 and #3085 exercised that current workflow on the state-sync PR and were terminal-green across all active validation jobs.
- PR #1009 (durable-state synchronization) is merged as `c41a071a345715f199bdade34872049faba4527d`; final closeout-state PR #1011 carries the final synchronized repository state.
- No implementation PRs are open. PR #925/#1008 runner experiments and stale sewing PR #999 were closed unmerged; #904 is the merged runner implementation.
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, and `shared` subpackages.
- Root Python files remain limited to `Init.py`, `InitGui.py`, and the CI `sitecustomize.py` hook.
- Canonical CI: `.github/workflows/canonical-execution.yml`; exactly one workflow is retained.
- CI policy: preserve the Docker/Xvfb FreeCAD path, runner fallback behavior, and fail-closed screenshot/evidence assertions; do not multiply workflows.

## Release evidence

- Exact-head run #3090 / `35815912414` passed Python/non-GUI, staged sewing creation, production pattern export, full tunic visual/simulation audit, and README turntable jobs. Benchmark and README publication are correctly skipped for a pull-request-triggered run.
- Final closeout validation artifact #10731910934 was directly inspected. It contains curved 1:1 and staged 2:2 M:N sewing acceptance, proportional physical correspondence, seam 2D/3D visual evidence, four-piece arrangement and native Garment hierarchy, Mannequin DrapeTarget, stress diagnostics, save/reload, explicit invalidation/repair, stale-export blocking, deterministic rerun and SVG/DXF export evidence.
- The final artifact contains six drape screenshots and simulation-quality/realtime-preview evidence. Drape metrics are finite, one connected component per panel, and classified structurally-plausible; front/rear screenshots were directly inspected.
- Earlier exact-head sewing run #3063 / `35809583435` independently passed the focused curved-M:N smoke. Its artifact #10729700651 records non-uniform curved sampling, 2:2 proportional physical lengths, explicit B reversal, correspondence severity/recovery GUI evidence, 2D/3D seam visuals, save/reload endpoint stability, stale-reference invalidation, and FreeSewing preview/commit/cancel.
- Current main contains the post-reload PatternPiece reacquisition fix originally tracked by stale PR #999.

## Architecture / project state

- FreeCAD remains authoritative for editable geometry and persistence; Cloth owns garment semantics; the solver owns physics.
- `PatternIR`, `SewingGraph`, `SimulationScene`, and `DrapeTarget` remain the semantic boundaries.
- Simulation-derived mesh/collision state is rebuildable and invalidated from authoritative upstream edits.
- Current main satisfies the release epic's canonical public-workbench garment lifecycle: Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output, including persistence, invalidation/repair, determinism and fail-closed export.
- The durable sewing correspondence/diagnostics closeout (#475) is complete and closed.
- Historical child issues for garment lifecycle, curved M:N sewing, canonical workflow preflight, stale workflow tracks, and lifecycle process termination have been reconciled and closed with explicit state reasons.
- The supervisor root #647, durable-state synchronization record #720, and release epic #471 are all closed with state reason `completed`. No open issue or pull request remains in the project release queue.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal status, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit state reason and a reason recorded in the conversation.

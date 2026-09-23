# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `60393fecbee814f56ed8018f648167eb461e9c0b`.
- The current mainline release gate is the merged canonical garment E2E change. Its validated source head was `40140b3a06549249c567feeb5e74dd5b766f551b`, exact-head canonical run #3076 / `35813109107`, terminal conclusion `success`.
- The merged release head `40140b3a06549249c567feeb5e74dd5b766f551b` is an ancestor of current main. Compare from that validated head to current main reports 12 commits ahead and zero file differences, so the validated implementation is unchanged by the later merge-only history.
- No implementation pull requests are open. Historical runner-preference PRs #904/#925/#1008 and stale sewing PR #999 were closed after audit; none is a release dependency.
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, and `shared` subpackages.
- Root Python files remain limited to `Init.py`, `InitGui.py`, and the CI `sitecustomize.py` hook.
- Canonical CI: `.github/workflows/canonical-execution.yml`; exactly one workflow is retained.
- CI policy: preserve the Docker/Xvfb FreeCAD path and all fail-closed screenshot/evidence assertions; do not multiply workflows.

## Release evidence

- Exact-head run #3076 / `35813109107` passed Python/non-GUI, staged sewing creation, production pattern export, full tunic visual/simulation audit, and README turntable jobs. Benchmark and README publication are correctly skipped for a pull-request-triggered run.
- Garment/tunic artifact #10730771278 was directly inspected. The artifact contains:
  - curved 1:1 and staged 2:2 M:N sewing acceptance;
  - physical proportional correspondence and zero maximum pair gap for the canonical fixture;
  - 3D and 2D seam markers;
  - four-piece arrangement and native Garment hierarchy;
  - Mannequin DrapeTarget and stress diagnostics;
  - save/reload persistence;
  - explicit native-edge invalidation and successful repair;
  - stale-export blocking;
  - deterministic rerun signature;
  - SVG/DXF export evidence;
  - final marker `canonical garment end-to-end acceptance passed`.
- The same artifact contains six drape screenshots and simulation-quality/realtime-preview evidence; visual acceptance is supported by finite, connected drape metrics and direct inspection of front/rear screenshots.
- Earlier exact-head sewing run #3063 / `35809583435` independently passed the focused curved-M:N smoke. Its sewing artifact #10729700651 records non-uniform curved sampling, 2:2 proportional physical lengths, explicit B reversal, correspondence severity/recovery GUI evidence, 2D/3D seam visuals, save/reload endpoint stability, stale-reference invalidation, and FreeSewing preview/commit/cancel.
- Current main already contains the post-reload PatternPiece reacquisition fix from stale PR #999.

## Architecture / project state

- FreeCAD remains authoritative for editable geometry and persistence; Cloth owns garment semantics; the solver owns physics.
- `PatternIR`, `SewingGraph`, `SimulationScene`, and `DrapeTarget` remain the semantic boundaries.
- Simulation-derived mesh/collision state is rebuildable and invalidated from authoritative upstream edits.
- Current main satisfies the release epic's canonical public-workbench garment lifecycle: Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output, including persistence, invalidation/repair, determinism and fail-closed export.
- The durable sewing correspondence/diagnostics closeout (#475) is complete and closed.
- Historical child issues for the garment process lifecycle, curved M:N sewing, canonical workflow preflight, and stale runner/workflow tracks have been reconciled and closed with explicit state reasons.
- Remaining open project records are the supervisor root #647, its durable-state synchronization task #720, and release epic #471. These are administrative closeout records, not unvalidated implementation work.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal status, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit state reason and a reason recorded in the conversation.

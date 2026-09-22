# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `5acc453e12e1462481b85df49ba16a9c31483ee1`.
- Latest verified canonical workflow: run #2520 / run ID `35782037267`, terminal-success on current main. All seven workflow jobs completed successfully.
- Latest verified canonical artifacts: `pattern-production-export` 10718573486, `sewing-creation-smoke` 10718403724, `tunic-visual-audit` 10718318860, `readme-turntables` 10718134220, `workbench-benchmark` 10717974490.
- Canonical CI workflow: `.github/workflows/canonical-execution.yml` (workflow blob `ad6c8789d91ce3ca34825f055087e75b976647b4`).
- Exactly one workflow exists under `.github/workflows/`.
- Canonical jobs: Python and FreeCAD non-GUI tests; Sewing staged creation smoke; Pattern production export smoke; Full tunic visual and simulation audit; README turntables; Publish README turntables; Measured FreeCAD workbench benchmark.
- CI policy: preserve the Docker/Xvfb FreeCAD path and do not add a second workflow.

## Current release / PR state

- #695 is open on current main (`5acc453e12e1462481b85df49ba16a9c31483ee1`), head `c339429a5ed5f5bbee097ae5e2f2b4fd1ba08859`; it is the active PatternIR runtime-boundary slice.
- #702 is open but stale against main (base `6b3733ec5f794e652fb03ef4db1d156ecf57c3cd`), head `de2cfbbf64c54c2f9e834137cd11677d5df93893`, and currently not mergeable.
- #704 is open on current main, head `b55029a2aca2be2a85b1ba68f5c94fac47579e11`; it is the focused single-scene PatternIR follow-up.
- #706 is open on current main, head `95db75ce1866c3a8d9f806cee11cfb79c5b9bfc9`; it is the current canonical garment E2E candidate.
- #711 is open but based on stale main `6b3733ec5f794e652fb03ef4db1d156ecf57c3cd`, head `1b7b294a13899f5d4a4e89510dc01b1a24ad19f5`; it overlaps the PatternIR simulation-boundary work and needs reconciliation before merge.
- #719 is open on current main, head `c239ae9857b0b3853b275139ba66889e7169b370`; it is the current pinned-stitch feasibility guard candidate.
- #721 is open on current main, head `aed954e897a38d68b7a42d90cf0647b7300be43e`; it is a bounded right-shoulder seam-edge A/B experiment.
- #722 is open on current main, head `87ac91766305257f5a0a96444eb68058eac598fb`; it is the bounded solver seam-sampling A/B experiment.
- #708 is closed without merge; its garment-E2E workflow addition is not part of current main. Treat its head `9ff93cbf56e56f90ea6b44ad7dd2c82f81de26cd` as historical.
- #701 is closed without merge; its hierarchy branch is not part of current main. Treat its head `f95f3ce6bf780e7a031c7b75276a782c36f64a5c` as historical.
- #472 is closed as complete; the current supervisor record no longer treats M0 visual trust as unresolved.

## Architecture invariants

- Package root: `freecad_cloth/`
- Domain packages: `avatar`, `pattern`, `sewing`, `simulation`
- Shared packages: `common`, `shared`
- Root Python files: `Init.py`, `InitGui.py`, `sitecustomize.py` only
- Root domain implementations and root compatibility shims are forbidden.
- FreeCAD owns editable geometry and persistence; Cloth owns semantics; the solver owns physics.
- `PatternIR`, `SewingGraph`, `SimulationScene`, and `DrapeTarget` remain the semantic boundaries.
- `trimesh` remains optional/lazy; CPU reference remains the correctness baseline.
- Tissu remains sandbox-only until runtime compatibility, constraint/collision parity, determinism, visual parity, and performance are demonstrated.

## Current focus

- The current main head and its canonical validation are terminal-green.
- Do not describe any open PR as merged without live GitHub confirmation.
- First reconcile overlapping PatternIR work in #695/#704/#711 and the stale sewing release slice #702.
- Keep #706 as the current canonical garment-E2E candidate without claiming garment E2E is on main until its exact head is validated and merged.
- Validate the current-main pinned-stitch guard #719 separately from diagnostic A/B experiments #721/#722.
- Continue release work through M1/M2 issues #473/#475/#476 after the active implementation queue is reconciled.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal state, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit state reason and a reason recorded in the conversation.

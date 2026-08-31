# Agent status

Machine-readable supervisor coordination record for implementation agents.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the existing Docker/Xvfb GUI screenshot and PNG export path. Do not create a second workflow.
- Current open-PR policy: every PR must be reviewed for scope, CI evidence, mergeability, and regression risk before merge.
- Supervisor audit: PR #366 and PR #368 have been reviewed and merged; current open PRs must remain gated on focused review plus canonical evidence.

## Release gates

1. Pattern -> Sewing -> Simulation works through public FreeCAD workbench commands.
2. Native Sketcher remains authoritative for editable pattern geometry.
3. Sewing remains semantic Cloth data and survives save/reload.
4. Invalid upstream topology produces explicit invalid state; never silently retarget seams.
5. Simulation consumes derived mesh + target-neutral collision data.
6. DrapeTarget is authoritative for collision selection; mannequin is one provider.
7. Real FreeCAD/Xvfb GUI acceptance remains mandatory.
8. GUI screenshots remain real 1280x720 PNG artifacts in canonical CI.
9. Changes to canonical CI require an explicit release-gate review and must remain narrowly scoped.

## Current supervisor queue

### P0 — release blockers

- Simulation tessellation/quality integration #347 is complete and merged through PR #368; keep particle-distance topology and GUI screenshot contracts covered.
- Resolve DrapeTarget stale-state safety and authority tracked by #322/#289/#284.
- Keep the canonical end-to-end fixture healthy (#155/#278).
- Finish native Sketcher acceptance and topology repair (#298/#297).

### P1 — workbench completeness

- Complete M:N/free sewing UX and curved correspondence repair (#275).
- Improve native workbench command/toolbar coverage (#344 and related UI slices).
- Apply the UI consistency audit (#267).
- Add production pattern authoring parity: grading, seam allowance, notches, grainline, internal marks, validation, export (#162).

### Avatar / draping

- Parametric mannequin service boundary: completed in #203; user-facing mannequin task panel and canonical acceptance continue in #369 / PR #370.
- Generic FreeCAD-object drape target: #228.
- Keep both behind the same target-neutral collision interface.
- Prototype the mannequin before higher-fidelity body generation; generic CAD targets should use the same collision provider boundary.

## Agent rules

- Re-cut implementation branches from current `main`; do not revive stale heads.
- Update this file when starting or handing off a substantial implementation slice.
- One issue = one focused implementation concern unless a dependency requires otherwise.
- No workflow multiplication.
- Preserve GUI screenshot/export behavior unless the issue explicitly targets it and the change is proven against the canonical gate.
- Prefer native FreeCAD APIs and document dependencies over custom parallel systems.
- Never hide a failing test or weaken an assertion to make CI green.
- Before merge: inspect changed files, review diff, verify Python tests, verify real FreeCAD/Xvfb where relevant, then merge and verify the merge.

## Current feature direction

Prototype -> MVP -> Production order is documented in `docs/PRODUCTION_PLAN_2026.md` and the detailed sewing/draping research in `docs/SEWING_WORKFLOW_RESEARCH.md`.

## Active implementation slices

- **Avatar GUI:** PR #371 is the current non-draft implementation slice for #369; it now uses staged Apply & Rebuild semantics, explicit UI→FreeCAD property mapping, and focused GUI contract coverage. Canonical FreeCAD/Xvfb acceptance remains required before merge.
- **DrapeTarget:** #228 remains the next target-neutral fitting slice after stale-state P0s are safe.
- **Pattern/Sewing:** active audit branches must be re-cut from current main before handoff; no stale head may be merged.
- **Pattern Sketcher-first:** issue #360 is claimed on branch `agent/pattern-sketcher-first-20260831`; implementation is limited to making native Sketcher the default Pattern creation/edit path, with focused tests and no workflow changes.

## Supervisor audit notes — 2026-08-31

- Reviewed all open PRs and merged only focused, evidenced PRs; no PR was closed without a reason.
- Closed issue #356 as completed after canonical GUI screenshot/PNG validation demonstrated the Task View bootstrap fix works.
- Closed issue #347 automatically through merged PR #368 after Python/FreeCAD and real Xvfb GUI execution succeeded.
- Confirmed the canonical workflow remains the sole CI workflow and retains the real FreeCAD/Xvfb screenshot/export checks.
- Research confirms that M:N sewing, staged cancellation, arrangement points, reset arrangement, superimpose, visible sewing direction and task-oriented tool grouping should be treated as workflow contracts, not decorative UI features.
- Human avatar and arbitrary FreeCAD geometry remain interchangeable providers behind the target-neutral collision boundary.

# Agent status

Machine-readable supervisor coordination record for implementation agents.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the existing Docker/Xvfb GUI screenshot and PNG export path. Do not create a second workflow.
- Current open-PR policy: every PR must be reviewed for scope, CI evidence, mergeability, and regression risk before merge.

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

- Repair simulation tessellation/quality integration tracked by issue #347.
- Resolve DrapeTarget stale-state safety and authority tracked by #322/#289/#284.
- Keep the canonical end-to-end fixture healthy (#155/#278).
- Finish native Sketcher acceptance and topology repair (#298/#297).

### P1 — workbench completeness

- Complete M:N/free sewing UX and curved correspondence repair (#275).
- Improve native workbench command/toolbar coverage (#344 and related UI slices).
- Apply the UI consistency audit (#267).
- Add production pattern authoring parity: grading, seam allowance, notches, grainline, internal marks, validation, export (#162).

### Avatar / draping

- Parametric human mannequin: #203.
- Generic FreeCAD-object drape target: #228.
- Keep both behind the same target-neutral collision interface.

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

Prototype -> MVP -> Production order is documented in `docs/PRODUCTION_PLAN_2026.md`.

## Active agent slice

- **2026-08-31:** `agent/workbench-registration-20260831` claimed issue #344.
- Scope: strengthen native Pattern/Sewing/Simulation workbench registration regression coverage, specifically Sewing menu group order/completeness and stable toolbar membership.
- Constraints: no workflow changes; no command implementation changes.

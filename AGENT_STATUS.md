# Agent status

Machine-readable supervisor coordination record for implementation agents.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the existing Docker/Xvfb GUI screenshot and PNG export path. Do not create a second workflow.
- Current open-PR policy: every PR must be reviewed for scope, CI evidence, mergeability, and regression risk before merge.
- Supervisor audit: PR #366, PR #368, and PR #372 have been reviewed and merged; PR #373 is the only currently open PR and is gated on terminal-green canonical evidence.

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

## Current release queue

### P0 — release blockers

- Resolve DrapeTarget stale-state safety and authority tracked by #322/#289/#284.
- Keep the canonical end-to-end fixture healthy (#155/#278).
- Finish native Sketcher acceptance and topology repair (#298/#297).
- Finish simulation quality/material lifecycle (#145) after the tessellation fix in merged PR #368.

### P1 — workbench completeness

- Complete M:N/free sewing UX and curved correspondence repair (#275).
- Improve native workbench command/toolbar coverage (#344 and related UI slices).
- Apply the UI consistency audit (#267).
- Add production pattern authoring parity: grading, seam allowance, notches, grainline, internal marks, validation, export (#162).

### Avatar / draping

- Parametric mannequin service boundary: completed in #203; staged mannequin task-panel slice merged as PR #372; #369 remains open until complete create -> edit -> rebuild -> landmark -> save/reload canonical acceptance is evidenced.
- Production avatar provider/fidelity ladder is tracked by #374; do not start high-fidelity body generation until #369 and target-neutral DrapeTarget acceptance are stable.
- Generic FreeCAD-object drape target: #228; mannequin and arbitrary CAD targets must remain interchangeable providers behind the same target-neutral collision interface.

## Agent rules

- Re-cut implementation branches from current `main`; do not revive stale heads.
- Update this file when starting or handing off a substantial implementation slice.
- One issue = one focused implementation concern unless a dependency requires otherwise.
- No workflow multiplication.
- Preserve GUI screenshot/export behavior unless the issue explicitly targets it and the change is proven against the canonical gate.
- Prefer native FreeCAD APIs and document dependencies over custom parallel systems.
- Never hide a failing test or weaken an assertion to make CI green.
- Before merge: inspect changed files, review diff, verify Python tests, verify real FreeCAD/Xvfb where relevant, then merge and verify the merge.

## Feature direction

Prototype -> MVP -> Production order is documented in `docs/PRODUCTION_PLAN_2026.md` and detailed sewing/draping research in `docs/SEWING_WORKFLOW_RESEARCH.md`.

### Prototype

Prove architecture and interaction contracts with a small multi-piece garment: native Sketcher PatternPiece, persistent semantic seams/marks, transactional segment/free/M:N representation, target-neutral DrapeTarget, deterministic arrangement/reset, preview mesh, CPU reference simulation, save/reload and explicit invalidation.

### MVP

Make the workflow repeatable: robust semantic edge identity, 1:N/M:N/free sewing and repair UX, arrangement points/wrap/superimpose/reset, parametric mannequin measurements/poses, generic CAD target selection, particle-distance/fabric presets, pinning and production-oriented 2D pattern export.

### Production

Only after the end-to-end contracts are stable: higher-fidelity replaceable human body provider, multiple collision targets, face/subelement targets, stress/strain/fit/pressure diagnostics, grading/nesting/manufacturing validation, advanced construction (pleats/folds, topstitch, buttons/tacks, linings/facings, modular blocks, POM), and optional solver backends.

## Current feature/UX contracts

- Pattern is the geometry authoring surface; Sketcher owns editable geometry and Cloth owns garment semantics.
- Sewing is a semantic assembly editor. M:N selection is transactional: staged selection, explicit completion, Delete cancels the latest stage, Esc cancels the operation, and invalid candidates are rejected visibly.
- Sewing direction/reversal and correspondence diagnostics are inspectable before commit and persist in the semantic seam.
- Arrangement is persistent fitting metadata plus deterministic FreeCAD `Placement`; transient previews must not become a second authority.
- Reset 2D/3D arrangement and superimpose are normal recovery/construction operations, not solver behavior.
- Simulation task panels use a clear action hierarchy: Run primary, Step secondary/debug, Reset recovery/destructive; quality/material values are persistent and unit-aware.
- Human mannequin and generic FreeCAD geometry are providers of the same DrapeTarget/CollisionSurface contract; solver code must not branch on mannequin identity.
- High-fidelity avatar work must preserve provider identity, measurements, pose, collision representation and deterministic invalidation across save/reload.

## Supervisor audit notes — 2026-08-31

- Re-checked repository PRs and issues. PR #373 is the only open PR; it is a focused Sewing registration test slice and has been left open because its exact head has no associated canonical workflow run yet. A review comment records the terminal-green evidence requirement.
- No PR or issue was closed without a reason. No stale PR was merged.
- Canonical workflow remains the sole workflow and retains the real FreeCAD/Xvfb screenshot/export path: four 1280x720 PNG states plus diagnostics. Do not edit that workflow casually.
- Merged PR #368 fixed simulation-quality tessellation by preserving authored boundary vertices and refining interiors; this remains a regression contract.
- Merged PR #372 provides the staged mannequin GUI. #369 still requires real canonical acceptance before the avatar workstream advances.
- Research baseline identifies M:N sewing, staged cancellation, visible sewing direction, arrangement points, reset arrangement, superimpose, collision-target interchangeability and task-oriented tool grouping as workflow contracts rather than decorative UI features.
- Production feature inventory includes grading, DXF-AAMA/ASTM/Standard DXF interoperability where licensing permits, fit maps, POM/measurement inspection, topstitching, pleats/folds, buttons/buttonholes/tacks, linings/facings, modular blocks and automatic sewing helpers. These remain downstream of the P0/P1 release gates.
- `ADVANCED_TOOL_MODE.md` is not present in the repository; supervisor execution policy is retained in `TOOL_STATE.md`.

## Handoff checklist

Every implementation issue should state:

- authoritative data model/API;
- files allowed to change;
- dependencies on other issues;
- required unit tests;
- required real-FreeCAD/Xvfb acceptance;
- screenshot/artifact expectations;
- explicit non-goals;
- whether canonical CI must remain byte-for-byte unchanged.

The supervisor merges only after those acceptance conditions are evidenced.

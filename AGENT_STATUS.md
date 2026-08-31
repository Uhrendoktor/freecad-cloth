# Agent status

Machine-readable supervisor coordination record for implementation agents.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the existing Docker/Xvfb GUI screenshot and PNG export path. Do not create a second workflow.
- Current open-PR policy: every PR must be reviewed for scope, CI evidence, mergeability, and regression risk before merge.
- Supervisor audit: PR #377 merged into `main`; duplicate PRs #373, #376, #375 and #379 were closed as superseded with explicit reasons. PR #378 was closed because it introduced workflow multiplication around the fragile screenshot path. PR #381 remains open pending a current-main recut and canonical evidence.

## Release gates

1. Pattern -> Sewing -> Simulation works through public FreeCAD workbench commands.
2. Native Sketcher remains authoritative for editable pattern geometry.
3. Sewing remains semantic Cloth data and survives save/reload.
4. Invalid upstream topology produces explicit invalid state; never silently retarget seams.
5. Simulation consumes derived mesh + target-neutral collision data.
6. DrapeTarget is authoritative for collision selection; mannequin is one provider.
7. Real FreeCAD/Xvfb GUI acceptance remains mandatory.
8. GUI screenshots remain real 1280x720 PNG artifacts in canonical CI.
9. Changes to canonical CI require an explicit release-gate review and must leave screenshot generation/validation semantics intact.

## Current release queue

### P0 — release blockers

- Resolve DrapeTarget stale-state safety and authority tracked by #322/#289/#284.
- Keep the canonical end-to-end fixture healthy (#155/#278).
- Finish native Sketcher acceptance and topology repair (#298/#297); the default Sketcher authoring slice from #360 is now merged as PR #383.
- Finish simulation quality/material lifecycle (#145) after the tessellation fix in merged PR #368.

### P1 — workbench completeness

- Complete M:N/free sewing UX and curved correspondence repair (#275).
- Apply the UI consistency audit (#267).
- Add production pattern authoring parity: grading, seam allowance, notches, grainline/internal marks, validation and export (#162/#360).
- Keep the Sewing command/toolbar contract covered after merged PR #377.

### Avatar / draping

- Parametric mannequin service boundary: completed in #203; staged mannequin task-panel slice merged as PR #372; #369 remains open until complete create -> edit -> rebuild -> landmark -> save/reload canonical acceptance is evidenced.
- Generic FreeCAD-object drape target: #228; mannequin and arbitrary CAD targets must remain interchangeable providers behind the same target-neutral collision interface.
- Production avatar provider/fidelity ladder is tracked by #374; do not start high-fidelity body generation until #369 and target-neutral DrapeTarget acceptance are stable.

## Agent rules

- Re-cut implementation branches from current `main`; do not revive stale heads.
- Update this file when starting or handing off a substantial implementation slice.
- One issue = one focused implementation concern unless a dependency requires otherwise.
- No workflow multiplication.
- Preserve GUI screenshot/export behavior unless the issue explicitly targets it and the change is proven against the canonical gate.
- Prefer native FreeCAD APIs and document dependencies over custom parallel systems.
- Never hide a failing test or weaken an assertion to make CI green.
- Before merge: inspect changed files, review diff, verify Python tests, verify real FreeCAD/Xvfb where relevant, then merge and verify the merge.
- Close stale/duplicate work only with an explicit reason recorded in the PR conversation; do not silently discard implementation scope.

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
- Production construction features such as grading, plotting, topstitch, buttons/buttonholes, pleats/folds, linings/facings and modular blocks remain downstream of the authoritative Pattern/Sewing/DrapeTarget contracts.

## Supervisor audit notes — 2026-08-31

- Re-checked all open PRs after the latest mainline merge. PR #381 remains the only open PR after closing stale/duplicate #375 and #379 and rejecting #378's workflow-multiplication approach. #381 is not mergeable yet and has no canonical workflow run for its exact head; do not merge until it is re-cut from current `main` and passes the canonical Python + FreeCAD/Xvfb gate.
- PR #383 is merged and supplies the native Sketcher default authoring path for #360; its canonical run 1049 passed before merge. Do not revive #379 or #375.
- Canonical workflow remains the sole workflow and retains the real FreeCAD/Xvfb screenshot/export path: four 1280x720 PNG states plus diagnostics. The screenshot generation/validation job is not to be weakened or replaced.
- Merged PR #368 fixed simulation-quality tessellation by preserving authored boundary vertices and refining interiors; this remains a regression contract.
- Merged PR #372 provides the staged mannequin GUI. #369 still requires real canonical acceptance before the avatar workstream advances.
- Research baseline confirms that CLO-style sewing is not just pairwise edges: Segment, Free, 1:N and M:N sewing use staged selection/commit, visible direction feedback, and explicit cancellation/rejection. Arrangement, reset and superimpose are fitting operations separate from solver behavior.
- Recent official CLO documentation also reinforces production needs: editable seam allowance behavior, notches with persistence/display rules, grading including notch grading, DXF interoperability, plotting, and modular/block sewing. These are production features, not reasons to expand the solver boundary.
- Added `docs/CLO_FEATURE_MATRIX_2026.md` and `docs/AGENT_HANDOFF_TEMPLATE.md` to make feature triage, UI/UX contracts, avatar-provider architecture and agent handoff requirements explicit.
- User-requested avatar direction is locked as two interchangeable providers: a recognizably human FreeCAD-native mannequin for normal garment fitting, and a generic FreeCAD Shape/PartDesign/Body/Mesh object through the same DrapeTarget interface. High-fidelity avatar work is later.
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

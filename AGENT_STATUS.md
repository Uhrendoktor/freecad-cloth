# Agent status

Machine-readable supervisor coordination record for implementation agents.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the existing Docker/Xvfb GUI screenshot and PNG export path. Do not create a second workflow.
- Open PRs at the latest audit: `0`.
- Latest audit record: `docs/SUPERVISOR_AUDIT_2026-08-31.md`.

## Release gates

1. Pattern → Sewing → Simulation works through public FreeCAD workbench commands.
2. Native Sketcher remains authoritative for editable pattern geometry.
3. Sewing remains semantic Cloth data and survives save/reload.
4. Invalid upstream topology produces explicit invalid state; never silently retarget seams.
5. Simulation consumes derived mesh + target-neutral collision data.
6. DrapeTarget is authoritative for collision selection; mannequin is one provider.
7. Real FreeCAD/Xvfb GUI acceptance remains mandatory where behavior changes.
8. GUI screenshots remain real 1280x720 PNG artifacts in canonical CI.
9. Canonical CI changes require explicit release-gate review and must retain screenshot generation/validation semantics.

## Current release queue

### P0

- DrapeTarget stale-state safety and authority: #322, #289, #284.
- Canonical end-to-end garment fixture: #155, #278.
- Native Sketcher acceptance/topology repair: #298, #297.
- Simulation quality/material lifecycle: #145.

### P1

- M:N/free sewing and curved correspondence repair UX: #275.
- Workbench registration/UI consistency: #344, #267.
- Pattern production parity: #162, #360.

### Avatar / draping

- Native mannequin acceptance #369: completed.
- Generic FreeCAD-object DrapeTarget #228: completed through merged PR #389; canonical run 1078 passed.
- Production avatar fidelity #374: defer until stale-target safety and the complete end-to-end target contract are stable.

### Production diagnostics

- Fit diagnostics and manufacturing validation: #362; defer until the end-to-end workflow and simulation/material contracts are stable.

## Prototype → MVP → Production

### Prototype

Prove boundaries with a small multi-piece garment: native Sketcher PatternPiece, persistent semantic seams/marks, transactional Segment/Free/M:N representation, target-neutral DrapeTarget, deterministic arrangement/reset, preview mesh, CPU reference simulation, save/reload and explicit invalidation.

### MVP

Make the workflow repeatable: robust semantic edge identity/topology repair, 1:N/M:N/free sewing UX, arrangement points/wrap/superimpose/reset, parametric mannequin measurements/poses, generic CAD target selection, particle-distance/fabric presets, pinning and production-oriented 2D export.

### Production

Only after public contracts are stable: higher-fidelity replaceable human provider, multiple collision targets, optional face/subelement targets, stress/strain/fit/pressure diagnostics, grading/nesting/manufacturing validation, advanced construction, and optional solver backends.

## UI/UX contracts

- Task panels: Context → Primary action → Secondary actions → Parameters → Recovery.
- Important state is persistent and inspectable in the document tree/Property Editor.
- Sewing stages selection before commit; Enter completes, Delete undoes the latest stage, Esc cancels; invalid candidates are visibly rejected.
- Sewing direction/reversal and correspondence diagnostics are inspectable before commit and persist in semantic seams.
- Arrangement is persistent fitting metadata plus deterministic FreeCAD Placement; transient previews are never a second authority.
- Simulation: Run primary, Step secondary/debug, Reset recovery. Target validity is visible before Run/Step.
- Quality/material settings are persistent and unit-aware and remain separate from collision-target selection.
- Stale state exposes an explicit reason and actionable recovery path.

## Avatar architecture

There are two interchangeable providers, not two solver paths:

```text
                    DrapeTarget
                   /           \\
        Human Mannequin      FreeCAD Geometry
        AvatarService         Shape/Body/Mesh
              \\                 /
               -> CollisionSurface -> Simulation
```

The mannequin remains a FreeCAD-native human provider with measurements, landmarks, poses and separate visual/collision representations. Generic Shape/PartDesign/Body/Mesh targets require no manual conversion. Both providers share target-neutral collision semantics and deterministic invalidation. High-fidelity body generation/import is a later provider behind the same contract.

## Agent rules

- Re-cut implementation branches from current `main`; do not revive stale heads.
- One issue = one focused implementation concern unless a dependency requires otherwise.
- No workflow multiplication.
- Preserve GUI screenshot/export behavior unless the issue explicitly targets it and the change is proven against the canonical gate.
- Prefer native FreeCAD APIs and document dependencies over custom parallel systems.
- Never hide a failing test or weaken an assertion to make CI green.
- Before merge: inspect changed files, review diff, verify Python tests, verify real FreeCAD/Xvfb where relevant, then merge and verify the merge.
- Close stale/duplicate work only with an explicit reason recorded in the PR conversation.

## Handoff checklist

Every implementation issue should state: authoritative data model/API; files allowed to change; dependencies; focused tests; real-FreeCAD/Xvfb acceptance; screenshot/artifact expectations; explicit non-goals; and whether canonical CI must remain byte-for-byte unchanged.

## Audit notes — 2026-08-31

- All open PRs were audited; there are currently none.
- Coordination issue #333 was closed as `completed` after the audit queue reached zero, with an explicit closing comment.
- PR #391 added the current supervisor audit/release-state documentation and was merged documentation-only; it did not change canonical CI.
- PR #389 added the native DrapeTarget task panel/public Edit/Refresh commands for #228; canonical run 1078 passed Python and real FreeCAD/Xvfb screenshot validation.
- Issue #369 is completed; the mannequin target contract and canonical acceptance slice are on main.
- PR #386 merged mannequin acceptance assertions after canonical run 1065.
- PR #385 merged arrangement-point foundation after canonical run 1062.
- PR #383 merged the native Sketcher-first authoring path after canonical run 1049.
- PR #393 added command-side stale-target safety: Simulation Step/Run now inspect the persistent DrapeTarget and refuse advancement with the target's actionable status before mutating Steps/recompute. Canonical run 1088 passed both Python/non-GUI and real FreeCAD/Xvfb screenshot/PNG validation. The deeper document-recompute guard in SimulationObjects remains part of #289 and is not claimed complete by this slice.
- Canonical workflow remains the sole workflow and retains four real 1280x720 PNG states plus diagnostics; its file hash remains unchanged at `90502f96c174ee2f30d09ce2fa92b3070d178751`.
- Research baseline: CLO-style sewing is staged/transactional across Segment, Free, 1:N and M:N; arrangement, reset and superimpose are fitting operations separate from solver behavior. Production priorities include seam allowance, notches, grading, DXF/plot output, fit maps and manufacturing validation.
- User-requested avatar direction remains two interchangeable providers: a recognizably human FreeCAD-native mannequin and generic FreeCAD Shape/PartDesign/Body/Mesh through the same DrapeTarget interface.
- `ADVANCED_TOOL_MODE.md` is not present in `Uhrendoktor/GPT-ToolsAndStorage`; current persistent tooling policy is recorded in `TOOL_STATE.md`.

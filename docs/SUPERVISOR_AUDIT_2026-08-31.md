# Supervisor audit — 2026-08-31

## Repository state

- Default branch: `main`.
- Open pull requests at audit time: **0**.
- Canonical CI workflow: `.github/workflows/canonical-execution.yml` only.
- The canonical GUI job still launches real FreeCAD under Xvfb at `1280x720`, exports four PNG states, validates PNG dimensions/signatures/size, and publishes screenshots only from `main` pushes.
- Do not add a second screenshot workflow, PR publisher, or repair workflow.

## Release order

1. **P0: DrapeTarget safety and authority** — #322, #289, #284. Ordinary document recompute must never crash merely because a persistent target became stale. Stale state must be explicit, collision data must not be consumed, and Run/Step must remain blocked until Refresh.
2. **P0: canonical garment fixture** — #155, #278. Keep one public Pattern → Sewing → Arrangement → Simulation → Save/Reload → Invalidate → Rebuild scenario as the release gate.
3. **P0: Sketcher acceptance/topology repair** — #298, #297. Sketcher remains authoritative; invalid semantic references fail closed and are repaired explicitly.
4. **P1: Sewing completion** — #275. Finish Segment/Free/1:N/M:N transactional selection, direction/reversal and correspondence repair UX.
5. **P0/P1: Simulation quality/material lifecycle** — #145. Particle distance, physical fabric properties, collision quality, pinning and visible simulation state.
6. **P1: Pattern production** — #162/#360. Seam allowance, notches, grainline/internal marks, grading and 2D export.
7. **Avatar acceptance** — #369. Complete create → edit → rebuild → landmark → save/reload acceptance for the native mannequin.
8. **Generic DrapeTarget** — #228. A normal FreeCAD Shape/Body/Mesh must be interchangeable with the mannequin behind the same target-neutral collision interface.
9. **Production avatar fidelity** — #374. Only after the target-neutral contract is stable.
10. **Production diagnostics/manufacturing** — #362. Stress/strain/fit/pressure analysis, grading review, DXF/plot/nesting and manufacturing validation after the core workflow is stable.

## CLO-style feature triage

### Prototype

Prove boundaries and interaction contracts with a small garment:

- native Sketcher-backed PatternPiece;
- semantic seam objects;
- Segment and Free sewing with staged/cancellable selection;
- early 1:N/M:N representation;
- explicit direction/reversal and curved correspondence diagnostics;
- persistent DrapeTarget with mannequin and generic-CAD providers;
- deterministic arrangement/reset;
- preview mesh and deterministic CPU reference simulation;
- save/reload and visible invalidation.

### MVP

Make the workflow repeatable:

- robust semantic edge identity and topology repair;
- 1:N/M:N/free sewing repair UX;
- arrangement points, wrap/superimpose/reset;
- parametric mannequin measurements and poses;
- generic CAD target selection;
- particle-distance and fabric presets;
- pinning and production-oriented 2D export.

### Production

Only after the public contracts are stable:

- higher-fidelity replaceable human provider;
- multiple collision targets and optional face/subelement targeting;
- stress/strain/fit/pressure diagnostics;
- grading/nesting/manufacturing validation;
- pleats/folds, topstitch, buttons/tacks, linings/facings, modular blocks and POM;
- optional solver backends.

## UI/UX contract

Every task panel should expose, in order:

1. **Context** — garment/piece/target and validity.
2. **Primary action** — the next workflow step.
3. **Secondary actions** — inspect/reversible edits.
4. **Parameters** — persistent, unit-aware values.
5. **Recovery** — Refresh/Repair/Reset with an explicit stale reason.

Sewing must stage selections before commit; `Enter` completes a stage, `Delete` undoes the latest stage, and `Esc` cancels. Invalid candidates are visibly rejected. Persistent seams are authoritative document data, not transient selection state.

Simulation must show target identity and validity before Run/Step. `Run` is primary, `Step` is secondary/debug, and `Reset` is recovery. Collision target, material and simulation quality are separate concerns.

## Avatar architecture

There are two providers, not two solver paths:

```text
                    DrapeTarget
                   /           \\
        Human Mannequin      FreeCAD Geometry
        AvatarService         Shape/Body/Mesh
              \\                 /
               -> CollisionSurface -> Simulation
```

The mannequin should remain recognizably human and FreeCAD-native, with measurements, landmarks, poses and separate visual/collision representations. Generic FreeCAD geometry must be accepted without manual conversion. Both providers share the same target-neutral collision contract and deterministic invalidation rules.

## Agent handoff requirements

Every implementation slice must state:

- authoritative data model/API;
- files allowed to change;
- dependencies;
- focused unit tests;
- real FreeCAD/Xvfb acceptance where relevant;
- screenshot/diagnostic expectations;
- explicit non-goals;
- whether `.github/workflows/canonical-execution.yml` remains byte-for-byte unchanged.

No stale branch is to be revived. Re-cut from current `main`, keep one focused concern per issue/PR, and never weaken tests to make CI pass.

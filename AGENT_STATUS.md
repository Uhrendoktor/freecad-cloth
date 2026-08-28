# Agent Work Registry

Coordination registry for supervisor-led work on `freecad-cloth`.

## Rules

1. Register before non-trivial implementation.
2. One scope, one owner; coordinate before touching another active scope.
3. Keep status, progress, tests and PR current.
4. CI/review/repository state are the authority for completion.
5. Mark completed or blocked work so no stale active entries remain.

## Active work

```yaml
- id: supervisor-release-20260828
  agent: supervisor
  task: Post-merge validation and issue/PR reconciliation
  status: validation
  files: [AGENT_STATUS.md, .github/workflows/canonical-execution.yml]
  scope: Validate current main after PR #94 and PR #97, close only completed issues, and leave no stale active work registry entries.
  started: 2026-08-28
  last_update: 2026-08-28T16:45:00Z
  progress: GUI documentation PR #94 merged; native adapter/benchmark PR #97 merged. Waiting for green post-merge canonical CI before final issue reconciliation.
  tests: canonical Python matrix, real FreeCAD smoke, GUI screenshots
  pr: 94, 97 (merged)
  blockers: post-merge CI
```

## Current issue map

- #68: GUI documentation screenshots — implemented and merged with PR #94.
- #71: garment-grade XPBD milestone — #82 completed; deterministic benchmark artifact now persisted by canonical CI.
- #75: native-library architecture umbrella — #85/#88 completed; #86/#87 already completed.
- #85: OCCT seam allowance adapter — implemented and smoke-tested in PR #97.
- #88: Placement/export adapter evaluation — documented and smoke-tested in PR #97.

## Completed issues

- #43 / #80: historical research snapshots — closed as superseded by focused records.
- #81: Sketcher-backed pattern editing — closed completed.
- #82: XPBD shear/bending/self-collision quality gates — closed completed.
- #83: optional Tissu/PositionBasedDynamics backend audit — closed completed; both remain optional.
- #86: MeshPart/Netgen triangulation adapter — merged as PR #93 and closed completed.
- #87: solver authority consolidation — merged as PR #91 and completed.

## Completed implementation milestones

- Workbench skeleton and canonical CI.
- Parametric pattern model and semantic construction metadata.
- Native Sketcher pattern adapter.
- Drafting UI, seam allowance and semantic export contracts.
- Sewing assembly and seam pairing.
- Parametric humanoid collision proxy plus imported FreeCAD body override.
- Deterministic drape quality gates and reference XPBD constraints.
- Native OCCT offset and native Placement audit.
- GUI documentation screenshot workflow with persisted artifacts.
- Deterministic reference drape benchmark artifacts in canonical CI.

## Supervisor policy

No issue is considered complete merely because code exists. Each implementation must have focused regression coverage, pass canonical Python CI, pass real FreeCAD smoke where applicable, and be reconciled with the issue registry before merge.

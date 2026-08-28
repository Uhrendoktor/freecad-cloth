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
- id: supervisor-ci-20260828
  agent: supervisor
  task: Canonical GUI documentation and release validation
  status: validation
  files: [tests/freecad_screenshot.py, .github/workflows/canonical-execution.yml, AGENT_STATUS.md]
  scope: Keep GUI screenshots deterministic and make benchmark artifacts part of canonical CI.
  started: 2026-08-28
  last_update: 2026-08-28T16:23:00Z
  progress: GUI screenshot PR #94 has been iterated after the first timeout; the latest run must complete before merge. Native adapter PR #96 also carries the persisted reference benchmark.
  tests: canonical Python matrix, real FreeCAD smoke, GUI screenshot workflow
  pr: 94, 96
  blockers: waiting for CI runners
```

## Current issue map

- #68: GUI documentation screenshots — implemented in PR #94, awaiting green CI.
- #71: garment-grade XPBD milestone — focused implementation #82 completed; benchmark artifact added to PR #96.
- #75: native-library architecture umbrella — focused audits #85/#88 are in PR #96.
- #85: OCCT seam allowance adapter — implemented and tested in PR #96.
- #88: Placement/export adapter evaluation — documented and tested in PR #96.

## Completed milestones

- #81 Sketcher-backed pattern editing — closed completed.
- #82 XPBD shear/bending/self-collision quality gates — closed completed; explicit reference XPBD constraints and deterministic tests are in `XPBD.py` / `tests/test_xpbd.py`.
- #83 optional Tissu/PositionBasedDynamics backend audit — closed completed; both remain optional due native build/ABI/runtime packaging constraints.
- #86 MeshPart/Netgen triangulation adapter — merged as PR #93.
- #87 solver authority consolidation — merged as PR #91.
- #43 / #80 historical research snapshots — closed as superseded by focused implementation/audit records.
- deterministic drape metrics and repeatability gates — merged previously as PR #84.
- default parametric humanoid collision and imported-body override — merged as PR #95.

## Supervisor policy

No issue is complete merely because code exists. Each implementation must have focused regression coverage, pass canonical Python CI, pass real FreeCAD smoke where applicable, and be reconciled with the issue registry before merge.

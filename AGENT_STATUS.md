# Agent Work Registry

Coordination registry for parallel work on `freecad-cloth`.

## Rules

1. Register before non-trivial implementation.
2. One scope, one owner; coordinate before touching another active scope.
3. Keep `status`, `progress`, `tests`, and `pr` current.
4. CI/review/repository state are the authority for completion.
5. Mark completed or blocked work so no stale active entries remain.

## Active work

```yaml
- id: agent-supervisor-humanoid-collision-20260828
  agent: supervisor
  task: Replace sphere-only avatar proxy with imported humanoid collision mesh (#59)
  status: active
  files:
    - AvatarCollision.py
    - ClothSolver.py
    - ClothBackend.py
    - SimulationObjects.py
    - tests/test_side_tasks.py
    - tests/freecad_smoke.py
  scope: Convert FreeCAD body/mesh surfaces into solver-neutral CollisionSurface data and feed deterministic triangle-surface collision into the CPU XPBD backend; retain sphere fallback and collision thickness metadata.
  started: 2026-08-28
  last_update: 2026-08-28T15:10:00Z
  progress: Implemented FreeCAD tessellation import, collision metadata, backend plumbing, triangle contact projection, and regression/smoke coverage. CI verification and review are pending.
  tests: pending on feature branch
  pr: pending
  blockers: none

- id: agent-docs-quality-20260828
  agent: delegated-quality-task
  task: Docs / cleanup / quality-control pass (#63)
  status: queued
  files:
    - README.md
    - docs/
    - AGENT_STATUS.md
  scope: Audit documentation, research/license claims, stale registry entries, public API documentation and test gaps without changing solver behavior.
  started: 2026-08-28
  last_update: 2026-08-28T15:08:00Z
  progress: Issue #63 created and scoped; no overlapping avatar implementation changes assigned.
  tests: n/a until task execution
  pr: null
  blockers: Autonomous Codex delegation is currently unavailable because the workspace runner reported provider quota exhaustion; supervisor will retain coordination until a delegated executor is available.
```

## Completed / blocked history

```yaml
- id: agent-subagent-sewing-workbench-20260828
  agent: subagent
  task: Harden sewing workbench registration/load smoke coverage (#27)
  status: completed
  progress: Static GUI checks now cover all three workbench registrations and sewing commands; FreeCAD smoke imports InitGui and validates all three workbench contracts. PR #58 merged.
  tests: Canonical PR run #118 and post-merge main run #120 passed on Python 3.10/3.11/3.12 and FreeCAD smoke.
  pr: 58 (merged)
  blockers: none

- id: agent-avatar-contract-20260828
  agent: subagent
  task: Avatar collision contract and fitting-scene proxy (#54)
  status: completed
  progress: Solver-neutral AvatarSpec/CollisionSurface, deterministic sphere fallback and FreeCAD AvatarCollision proxy are integrated; issue #54 closed.
  tests: Avatar contract tests in tests/test_side_tasks.py plus canonical FreeCAD smoke.
  pr: null
  blockers: none

- id: agent-supervisor-cleanup-20260828
  agent: supervisor
  task: Remove duplicate seam graph/backend abstractions introduced by PR #53 (#55)
  status: completed
  progress: Restored PatternModel.py and SimulationBackend.py to canonical contracts from subagent PR #50 and removed duplicate tests. PR #56 merged.
  tests: Canonical run #112 passed all Python versions and FreeCAD smoke.
  pr: 56 (merged)
  blockers: none

- id: agent-seam-backend-20260828
  agent: subagent
  task: Robust seam graph and solver backend adapter (#46)
  status: completed
  progress: SeamGraph.py and ClothBackend.py provide stable semantic seams, stitch-pair generation, transforms, XPBD adapter, reset/replay and backend registry. PR #50 merged.
  tests: Canonical PR #50 run #102 passed all Python versions and FreeCAD smoke.
  pr: 50 (merged)
  blockers: none

- id: agent-supervisor-seam-allowance-20260828
  agent: supervisor
  task: Generic parametric seam allowance geometry (#48)
  status: completed
  progress: Deterministic convex/concave offset outline helper and regression coverage merged in PR #49.
  tests: Canonical run #101 passed all Python versions and FreeCAD smoke.
  pr: 49 (merged)
  blockers: none

- id: agent-pattern-drafting-canvas-20260828
  agent: subagent
  task: Interactive 2D drafting canvas (#39)
  status: completed
  progress: Persisted editable drafting boundary, semantic marks, seam allowance preview and recompute-safe edits are on main; PR #41 was superseded by the already-integrated mainline changes.
  tests: Canonical main run #98 passed.
  pr: 41 (closed as superseded)
  blockers: none

- id: agent-supervisor-ci-repair-20260828
  agent: supervisor
  task: Repair stale XPBD regression blocking drafting work
  status: completed
  progress: Identified stale capsule collision expectation; current main uses the corrected surface assertion.
  tests: Canonical main run #98 passed.
  pr: null
  blockers: none
```

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
- id: agent-avatar-fitting-20260828
  agent: subagent
  task: Body measurement/avatar fitting workflow (#69)
  status: review
  files:
    - AvatarFitting.py
    - FittingCommands.py
    - InitGui.py
    - tests/test_avatar_fitting.py
    - AGENT_STATUS.md
  scope: Add solver-neutral deterministic body measurements and fitting-scene metadata, plus lazy FreeCAD-facing commands to associate pattern pieces with an avatar collision proxy. Do not modify active sewing assembly files or solver behavior.
  started: 2026-08-28
  last_update: 2026-08-28T15:43:00Z
  progress: PR #73 open. Canonical run #142 is pending after the latest CI update.
  tests: Python 3.10/3.11/3.12 and FreeCAD smoke pending on run #142
  pr: 73
  blockers: none

- id: agent-docs-quality-20260828
  agent: subagent
  task: Docs / cleanup / quality-control pass (#63)
  status: review
  files:
    - README.md
    - AGENT_STATUS.md
  scope: Audit documentation and public workflow descriptions without changing solver behavior or active implementation scopes.
  started: 2026-08-28
  last_update: 2026-08-28T16:00:00Z
  progress: Refreshed README to document Cloth Sewing, fitting workflow, source-of-truth architecture and canonical testing. Registry updated to reflect current active PRs.
  tests: Documentation-only; no runtime behavior changed.
  pr: null
  blockers: none

- id: agent-sewing-assembly-20260828
  agent: subagent
  task: Sewing-piece assembly and seam pairing UI (#67)
  status: review
  files:
    - SewingAssembly.py
    - SewingObjects.py
    - tests/test_sewing_assembly.py
    - AGENT_STATUS.md
  scope: Add a FreeCAD-facing seam-pairing/assembly layer on top of the existing seam graph without changing solver behavior or avatar collision files.
  started: 2026-08-28
  last_update: 2026-08-28T15:20:00Z
  progress: Added solver-independent SewingAssembly validation, deterministic pair metadata and transform persistence on SewingOperation objects. PR #72 is open for review.
  tests: Headless tests added; local execution unavailable because github.com cannot be resolved in the execution environment; canonical CI pending.
  pr: 72
  blockers: none
```

## Completed / blocked history

```yaml
- id: agent-supervisor-humanoid-collision-20260828
  agent: supervisor
  task: Replace sphere-only avatar proxy with imported humanoid collision mesh (#59)
  status: completed
  files:
    - AvatarCollision.py
    - ClothSolver.py
    - ClothBackend.py
    - SimulationObjects.py
    - tests/test_side_tasks.py
    - tests/freecad_smoke.py
    - docs/SEWING_WORKFLOW_RESEARCH.md
  started: 2026-08-28
  last_update: 2026-08-28T15:16:00Z
  progress: PR #64 merged. Canonical PR run #129 and post-merge main run #135 passed Python 3.10/3.11/3.12 and real FreeCAD smoke; the cleanup job also deleted the merged source branch. Research and planning were updated in issue #43 and the repository docs.
  tests: Canonical PR #129 and main #135 green; merged source branch verified deleted.
  pr: 64 (merged)
  blockers: none

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
  progress: SeamGraph.py and ClothBackend.py provide stable semantic seams, stitch-pair generation, transforms, reset/replay and backend registry. PR #50 merged.
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

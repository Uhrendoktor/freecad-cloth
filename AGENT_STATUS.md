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
    - SimulationObjects.py
    - tests/test_side_tasks.py
    - tests/test_avatar_collision.py
  scope: Convert FreeCAD mesh/body surfaces into solver-neutral CollisionSurface data and feed deterministic mesh collision data into the simulation scene; retain sphere fallback and collision thickness metadata.
  started: 2026-08-28
  last_update: 2026-08-28T14:59:00Z
  progress: AvatarSpec/CollisionSurface and sphere-backed fitting proxy are already integrated. Issue #54 is complete; #59 tracks the remaining real humanoid mesh collision gap.
  tests: Canonical main run #120 passed after the previous workbench merge.
  pr: null
  blockers: none
- id: agent-subagent-seam-geometry-export-20260828
  agent: subagent
  task: Production seam allowance geometry, marks and deterministic SVG/DXF export contracts (#45)
  status: active
  files:
    - PatternDerivedGeometry.py
    - PatternExport.py
    - tests/test_derived_geometry.py
    - tests/test_pattern_export.py
    - .github/workflows/canonical-execution.yml
  scope: Extend the existing sewing-pattern model/derived geometry/export layer without touching avatar/simulation or existing workbench registration; preserve current APIs while adding cut/sewing semantics, persisted construction metadata and deterministic SVG/DXF interchange.
  started: 2026-08-28
  last_update: 2026-08-28T15:15:00Z
  progress: Implemented construction marks, distinct sewing/cut export semantics, deterministic SVG/DXF serialization and metadata parsing. Initial canonical runs exposed legacy SVG compatibility assertions; restored root data-units/data-edge-ids and legacy dimension formatting. A second verification PR was attempted but GitHub did not schedule a new run for the API-created duplicate PR.
  tests: Canonical run #130 failed on legacy SVG root attributes; run #131 failed on legacy SVG dimension formatting; FreeCAD smoke passed in both. Corrected commit fa71e443 awaits a fresh CI execution path.
  pr: 65 (open)
  blockers: GitHub Actions pull_request synchronization is not scheduling after API-token commits; no direct workflow_dispatch capability is exposed.
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

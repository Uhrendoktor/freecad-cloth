# Agent Work Registry

This file is the coordination registry for parallel agents working on `freecad-cloth`.

## Purpose

Register active work before making implementation changes so agents can see what is already being worked on and avoid duplicate or conflicting work.

## Rules

1. **Register before coding.** Add/update an entry before starting a non-trivial task.
2. **One scope, one owner.** An agent owns only the files/components listed in its entry unless it first coordinates with the current owner.
3. **Keep the entry current.** Update `status`, `progress`, `files`, and `last_update` when scope changes or work reaches a meaningful milestone.
4. **Avoid duplicate work.** If an active entry covers the intended task, coordinate with that agent instead of starting a parallel implementation.
5. **QC is independent.** QC/review agents may inspect any area, but should avoid changing implementation files owned by another active agent unless fixing an urgent defect or explicitly taking ownership.
6. **Release the scope.** Mark work `completed` or `blocked` when finished; do not leave stale active entries.
7. **PRs must reference the registry entry.** Include the task/agent ID in the PR description or commit message when practical.
8. **The registry is coordination metadata, not proof of completion.** CI, tests, code review, and repository state remain the authority for completion.

## Status values

- `planned` — intended work, not started
- `active` — currently being implemented
- `review` — implementation complete, awaiting review/verification
- `blocked` — cannot proceed; record the reason
- `completed` — implementation and required verification finished

## Entry format

Copy this template for a new task:

```yaml
- id: agent-<short-id>
  agent: <agent name or handle>
  task: <short task description>
  status: active
  files:
    - <path>
  scope: <specific responsibility and boundaries>
  started: <YYYY-MM-DD>
  last_update: <YYYY-MM-DDTHH:MM:SSZ>
  progress: <current state>
  tests: <tests run / planned>
  pr: <PR number or null>
  blockers: <none or blocker description>
```

## Active work

```yaml
- id: agent-supervisor-avatar-20260828
  agent: supervisor
  task: Avatar/body collision proxy import and fitting setup (#54)
  status: active
  files:
    - AvatarModel.py
    - SimulationObjects.py
    - tests/test_avatar_model.py
    - AGENT_STATUS.md
    - TOOL_STATE.md
  scope: Define solver-neutral avatar metadata/collision proxy contract and deterministic fitting-scene setup; do not couple the document model to a specific solver.
  started: 2026-08-28
  last_update: 2026-08-28T14:51:00Z
  progress: Seam graph/backend architecture from subagent PR #50 is canonical. Supervisor duplicate abstractions were audited and removed by corrective PR #56.
  tests: Corrective PR #56 canonical run #112 passed on Python 3.10/3.11/3.12 and FreeCAD smoke.
  pr: null
  blockers: none
```

## Completed / blocked history

- id: agent-subagent-sewing-workbench-20260828
  agent: subagent
  task: Harden sewing workbench registration/load smoke coverage (#27, workbench slice)
  status: review
  files:
    - InitGui.py
    - tests/test_gui_structure.py
    - tests/freecad_smoke.py
    - AGENT_STATUS.md
  scope: Own only workbench discovery/registration and FreeCAD runtime smoke assertions; do not modify pattern/simulation/sewing object models or canonical workflow logic.
  started: 2026-08-28
  last_update: 2026-08-28T16:58:00Z
  progress: PR #58 opened. Static GUI checks now cover all three workbench registrations and sewing GUI/commands; real FreeCAD smoke imports InitGui and validates all three workbench contracts.
  tests: Canonical CI triggered by PR #58; local execution unavailable in this environment.
  pr: 58
  blockers: none

- id: agent-supervisor-cleanup-20260828
  agent: supervisor
  task: Remove duplicate seam graph/backend abstractions introduced by PR #53 (#55)
  status: completed
  files:
    - PatternModel.py
    - SimulationBackend.py
    - tests/test_simulation_backend.py
  scope: Restore canonical contracts supplied by subagent PR #50 and remove redundant supervisor additions.
  started: 2026-08-28
  last_update: 2026-08-28T14:51:00Z
  progress: Audit found PR #50 already contained the superior SeamGraph.py/ClothBackend.py implementation. PR #56 restored the pre-#53 contracts and removed duplicate tests.
  tests: Canonical run #112 passed all Python versions and FreeCAD smoke.
  pr: 56 (merged)
  blockers: none

- id: agent-supervisor-seam-graph-20260828
  status: completed
  progress: Supervisor duplicate seam-graph/backend slice was superseded by the canonical subagent implementation and then cleaned up in PR #56.
  tests: Canonical corrective run #112 passed.
  pr: 53 (merged, corrected by #56)
  blockers: none

- id: agent-seam-backend-20260828
  agent: subagent
  task: Implement robust seam graph and solver backend adapter (#46)
  status: completed
  files:
    - SeamGraph.py
    - ClothBackend.py
    - tests/test_seam_graph.py
    - tests/test_backend_adapter.py
    - AGENT_STATUS.md
  scope: FreeCAD-independent seam graph validation/assembly metadata and a stable simulation backend adapter around the existing ClothSystem; did not modify supervisor-owned pattern geometry files.
  started: 2026-08-28
  last_update: 2026-08-28T16:48:00Z
  progress: Implemented seam graph validation, normalized/reversed stitch-pair generation, persistent assembly transforms, XPBD backend adapter, deterministic reset/replay, and named backend registry. PR #50 merged to main.
  tests: Canonical PR #50 run #102 passed on Python 3.10/3.11/3.12 and FreeCAD smoke.
  pr: 50 (merged)
  blockers: none

- id: agent-supervisor-seam-allowance-20260828
  status: completed
  progress: Generic deterministic seam-allowance outline geometry merged as PR #49; issue #48 completed.
  tests: Canonical run #101 passed on Python 3.10/3.11/3.12 and FreeCAD smoke.
  pr: 49 (merged)
  blockers: none

- id: agent-pattern-drafting-canvas-20260828
  status: completed
  progress: Interactive drafting canvas and persisted semantic drafting metadata are integrated on main; PR #41 was superseded and closed after audit.
  tests: Canonical main run #98 passed; FreeCAD smoke passed in the same run.
  pr: 41 (closed as superseded)
  blockers: none

- id: agent-simulation-gui-20260828
  status: completed
  progress: Reviewed issue #31 and current main; simulation workbench GUI and persistent cloth/avatar/pin/seam controls were already integrated, so no duplicate implementation was merged.
  tests: Existing GUI structure and simulation scene contracts inspected; no new repository changes retained.
  pr: null
  blockers: none

- id: agent-supervisor-ci-repair-20260828
  status: completed
  progress: Audited failed PR validation; stale capsule expectation was identified and corrected on the obsolete PR branch. Current main contains the corrected 3.5 surface assertion and canonical main run #98 was green.
  tests: Canonical main run #98 passed.
  pr: null
  blockers: none

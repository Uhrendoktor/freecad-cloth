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
- id: agent-supervisor-seam-allowance-20260828
  agent: supervisor
  task: Implement generic parametric seam-allowance outline geometry (#48)
  status: active
  files:
    - PatternGeometry.py
    - tests/test_pattern_geometry.py
    - AGENT_STATUS.md
    - TOOL_STATE.md
  scope: FreeCAD-independent offset outline for ordered closed boundaries; preserve pattern source-of-truth and existing rectangle object behavior.
  started: 2026-08-28
  last_update: 2026-08-28T14:45:00Z
  progress: Mainline drafting milestone is green; next slice is generic allowance geometry before export work.
  tests: Existing canonical run #98 green; new geometry tests planned.
  pr: null
  blockers: none
```

## Completed / blocked history

```yaml
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
  progress: Audited failed PR validation; stale capsule expectation was identified and corrected on the obsolete PR branch. Current main already contains the corrected 3.5 surface assertion and canonical run #98 is green.
  tests: Canonical main run #98 passed.
  pr: null
  blockers: none
```

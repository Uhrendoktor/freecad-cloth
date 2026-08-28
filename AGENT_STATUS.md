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
# Agents add their entries here before starting work.
[]
```

## Completed / blocked history

Keep only a short recent history here. Detailed history belongs in commits and PRs.

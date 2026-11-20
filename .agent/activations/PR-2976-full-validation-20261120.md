# Guarded full-validation activation: PR #2976 — native avatar pose dragger lifecycle

- Target PR: #2976
- Target branch: `agents/avatar-pose-dragger-lifecycle-followup`
- Exact target head inspected: `0c72c13db782ff3680f0bad82aae0c3cca95c0ca`
- Current main: `f3dd115c3da1a7dea956b1f422a3cbfadd1bd278`
- Branch relation: 4 commits ahead and 0 behind current main.

## Commit-validation result for the exact current head

Run #44753085120:
- Pinned FreeCAD/PBD image build passed.
- Strict repository, architecture, workflow and security gate passed after the one Ruff formatting fix.
- Changed-Python annotation ratchet passed (no annotation or generic-object debt increase).
- Pyright: 0 errors, 0 warnings, 0 informations.
- Ruff format and Ruff lint passed.
- PR duplication gate passed.
- Commit-validation workflow skipped the targeted UI regression and full Python/FreeCAD GUI acceptance matrices, so this is not yet the complete acceptance required for merge.

## Follow-up changes in PR #2976

1. Stop and clear the Qt-owned dragger poll timer before removing native Coin nodes in `_remove_gizmo`.
2. Make same-joint selection idempotent: if the selected joint already has a gizmo, update the compact panel selection fields but do not rebuild its Coin scene graph.
3. Defer the post-drag preview rebuild with `QTimer.singleShot(0, ...)`, so native Coin dragger fields are not read or destroyed during the same polling callback.
4. Add regressions for poller shutdown before node teardown and same-joint selection without gizmo recreation.
5. Remove the redundant selection immediately before the Pose Mode GIF/drag recorder; the screenshot fixture already selects that joint.
6. Add progress markers around dragger selection, recorder startup, and native pointer press to localize any subsequent Pivy native crash.

## Context from the merged PR #2955

PR #2955 merged at `8ee563a0a9f56f4f79a6a83ba1f93ca3d896787c`. Its exact-head run passed strict repository checks, pytest, GUI Python validation, and avatar shape-editor GUI acceptance, but Pose Mode exited with SIGSEGV inside Pivy's `getField` when entering the drag phase. The new lifecycle guards specifically address timer/scene-graph overlap. Shape-editor focused-field teardown had passed and must remain green.

## Requested operation

Use the existing main-only guarded-rebase broker to replay the exact current PR #2976 head onto current main (the branch is already directly based on the stated current main SHA) and dispatch the repository's full exact-head validation workflow. Preserve the complete PR change set and update its branch only through the broker's force-with-lease mechanism if a replay is necessary.

Do not change the canonical workflow, weaken checks, or merge PR #2976 as part of this activation.

## Full acceptance required before merge

- Strict repository-quality, architecture, workflow/security, annotation-ratchet, Ruff format/lint and PR duplication checks pass.
- Targeted UI regression modules, full pytest and GUI Python validation pass.
- Shape editor GUI acceptance passes focused Height-field teardown, including `avatar-measurement-focus-teardown=passed field=height detached=true`, with no deleted-QDoubleSpinBox traceback.
- Pose Mode GUI acceptance completes without process crash or SIGSEGV.
- Pose acceptance progress log proves:
  - same-joint selection does not recreate native draggers;
  - timer and native dragger references remain valid through the pointer gesture;
  - the X-axis ring is the active dragger;
  - a non-zero staged X-angle delta is produced from real X11/XTest viewport press/move/release events;
  - the deferred preview rebuild completes after drag finish.
- Inspect the resulting avatar-pose screenshots and GIF, the shape-editor evidence, and complete logs.
- Review the final PR head, all exact-head checks and visual evidence before merging.

The activation PR squash-merge title must be exactly:
`RUN REBASE: PR #2976`

# CI configuration

The repository has one authoritative default for the FreeCAD application runtime budget.

## Authoritative setting

The default value lives in `pyproject.toml`, in the `[tool.freecad_cloth.ci]` table under
`freecad_application_timeout_seconds`. The normal budget remains **120 seconds** and should not
be raised globally to make a slow test pass.

The cube simulation collision ladder is the sole explicit exception because its five-rung diagnostic
was observed to time out at rung 5 after rungs 1–4 completed with finite results. Only that invocation
requests 360 seconds. The override is bounded to 360 seconds and passed through the composite action
to both the container and FreeCAD process. Simulation settings and acceptance thresholds remain unchanged.

## Consumers

The reusable FreeCAD test action defaults to 120 seconds and only sets
`FREECAD_APPLICATION_TIMEOUT_SECONDS` when a caller explicitly requests a non-default budget.
`tools/ci/run_freecad.py` reads the configured default from `pyproject.toml` unless that validated,
scoped environment override is present. The container budget is the separate outer bound; it defaults
to 120 seconds and permits at most 360 seconds for the documented diagnostic exception.

## What the timeout applies to

The **application budget** covers a single FreeCAD acceptance, screenshot or simulation invocation.
It is distinct from infrastructure budgets such as container setup, image pulls/builds and artifact publication.

## Changing the budget

Change the single default value in `pyproject.toml`, then run:

```bash
python tools/ci/timeout_contract.py
```

Use an explicit action input only for a documented diagnostic requiring more time. Do not introduce
per-test script timers or duplicated workflow defaults.

## Repository retention policy

The canonical workflow's retention job runs daily at 03:00 UTC on the repository's
`self-hosted/linux/x64/docker` runner. A one-shot run can also be activated by a
commit pushed to `main` whose title starts with `RUN MAINTENANCE CLEANUP`. A same-repository PR whose title starts with the same
phrase can also activate the job before merge; fork PRs cannot. These PRs use a
cleanup-only execution mode: the cleanup job runs first on the local runner, and its
successful completion is the required validation result for that maintenance PR.
The full GUI/simulation matrix is not dispatched for this operation. PR-triggered
cleanup uses `--runs-only` to retain the newest 10 completed workflow runs across
the repository, deleting the oldest completed runs first. It does not delete queued or
in-progress runs. The daily scheduled maintenance path continues to apply its separate
30-day workflow, branch, and container-package retention policies. The cleanup step
passes the workflow token to the GitHub CLI; repository write permissions alone do
not authenticate `gh`. It never consumes Microsoft-hosted runner minutes.

The cleanup script uses conservative age and reference checks:

- Delete unprotected source branches in any namespace when their latest commit activity is older than
  7 days, excluding the default branch, open pull-request heads, and `simulation-evidence/*` refs.
  A branch can also be deleted sooner if its current SHA exactly matches a closed PR head SHA from
  the same repository. Evidence refs are retained because PR comments link directly to their files.
  Missing or unverifiable activity is retained. Process the oldest eligible branches first, up to
  250 deletions per execution, and report stale branches left pending.
- Delete only completed Actions runs older than 30 days, oldest first, up to 100
  runs per execution. Active/queued runs are not selected.
- Prune at most 50 PBD validation container versions per execution, and only when
  their versions are older than 30 days and their immutable tags are not used by
  `main`, open pull-request heads, or recent/active workflow-run commits. Missing
  or unverifiable tag metadata is retained.
- The `freecad-ci` base image is not a target of package cleanup.

If a run fails, inspect the maintenance job log before retrying. A failed listing
or permission check should stop cleanup before deletions; do not replace these checks
with age-only deletion.

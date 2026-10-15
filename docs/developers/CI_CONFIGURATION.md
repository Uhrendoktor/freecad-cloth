# CI configuration

The repository has one authoritative setting for the FreeCAD application runtime budget.

## Authoritative setting

The value lives in `pyproject.toml`, in the `[tool.freecad_cloth.ci]` table under
`freecad_application_timeout_seconds`. That file is the sole source for the runtime limit.

Change the value in `pyproject.toml` when the accepted FreeCAD application budget changes.

The number must not be copied into documentation, individual test scripts or multiple workflow defaults. CI consumers are expected to read or validate against this setting.

## Consumers

The reusable FreeCAD test action no longer defines a second application timeout. Canonical workflow jobs do not pass one either. `tools/ci/run_freecad.py⟧ reads the configured value directly from `pyproject.toml⟧.

The separate container timeout remains infrastructure policy and is intentionally independent from the FreeCAD application budget.

## What the timeout applies to

The **application budget** covers a single FreeCAD acceptance, screenshot or simulation invocation.

It is distinct from infrastructure budgets such as container setup, image pulls/builds and artifact publication.

## Changing the budget

Change the single value in `pyproject.toml`, then run:

```bash
python tools/ci/timeout_contract.py
```

Changing that one value changes the effective FreeCAD application budget without a search-and-replace across workflow jobs.

## Repository retention policy

The canonical workflow's retention job runs daily at 03:00 UTC. A one-shot run can
also be activated by a commit pushed to `main` whose title starts with
`RUN MAINTENANCE CLEANUP`. The cleanup step passes the workflow token to the GitHub
CLI; repository write permissions alone do not authenticate `gh`.

The cleanup script uses conservative age and reference checks:

- Delete only `agent/*` branches whose latest commit activity is older than 14 days
  and whose branch is not the head of an open pull request.
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

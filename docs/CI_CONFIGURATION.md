# CI configuration

The repository has one authoritative setting for the FreeCAD application runtime budget.

## Authoritative setting

The value lives in `pyproject.toml`:

```toml
[tool.freecad_cloth.ci]
freecad_application_timeout_seconds = 55
```

Change that value when the accepted FreeCAD application budget changes.

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

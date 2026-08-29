# AGENT STATUS

## Active Work

- `agent/sewing-command-adapter-20260828` — Sewing/Fitting command adapter cleanup (PR #99).
- `agent/gui-screenshot-fix-20260829` — PR #101 GUI screenshot CI repair.

## Coordination

- Avoid modifying files owned by another active agent unless fixing a blocking integration failure.
- Record new implementation scopes here before editing shared infrastructure.
- Canonical CI workflow: `.github/workflows/canonical-execution.yml`.

## Completed

- `agent/gui-screenshot-fix-20260829` — fixed FreeCAD GUI screenshot macro startup by removing unsupported `FreeCADGui.showMainWindow()` calls and shortened the screenshot wait loop to 30 seconds after CI exposed the actual runtime failure.

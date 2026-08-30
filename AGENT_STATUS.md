# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

P0 supervision is focused on making the public FreeCAD Pattern -> Sewing -> Simulation workflow authoritative end-to-end. Before each implementation slice, open PRs and active issues are re-audited and subagent proposals are incorporated. The canonical CI workflow is reused; no duplicate workflow is permitted.

Current supervisor implementation branch: `agent/fix-sewing-gui-registration-20260830`.

### Current plan

1. Repair Sewing workbench GUI command grouping and real-FreeCAD activation.
2. Verify the headless GUI registration contract and the canonical FreeCAD/Xvfb screenshot path.
3. Hand off through a PR for canonical FreeCAD/Xvfb verification.
4. Continue DrapeTarget authority work only after canonical CI is green.

## Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is geometry authority; PatternIR is solver-neutral.
- **P0-B Sewing:** semantic references, curved correspondence, M:N sewing and repair UX are implemented; canonical verification remains required.
- **P0-C Human fitting:** persistent anthropometric mannequin and collision provider are implemented and previously smoke-tested.
- **P0-D Drape target:** persistent target-neutral DrapeTarget is implemented for mannequin and arbitrary FreeCAD Shape/Mesh. **Next work: make Simulation consume it directly.**
- **P0-E Simulation:** deterministic mesh/solver and lifecycle/status controls exist. **Current blocker remains target-authoritative collision rebuild after CI recovery.**

## Active workstreams

| Workstream | Issue | Status |
|---|---:|---|
| Sewing GUI registration / Xvfb activation | #308 | **in progress — deterministic command grouping and icon validation** |
| Canonical Actions control plane | #293/#306 | in progress / acceptance gate |
| DrapeTarget authority | #276/#304 | queued behind CI recovery |
| Canonical garment E2E | #278 | queued after target authority |
| Curved sewing repair acceptance | #275/#301 | implementation present; canonical verification pending |
| Pattern authoring production minimum | #162/#300 | active audit; avoid duplicate drafting kernel |
| Simulation quality/materials | #145 | active P0 integration |
| Export/package/install | #163/#147 | release follow-up |

## Sewing GUI registration finding

The Sewing workbench declared `ClothSewing_RepairSeam` in `SewingCommands.COMMANDS` but did not include it in `SEWING_COMMAND_GROUPS`, while `Initialize()` required the two sets to be identical. The resulting `ValueError` occurred during real FreeCAD workbench initialization. The repair places `ClothSewing_RepairSeam` in the existing `Validation & View` group, validates the command registry before mutating menus/toolbars, and retains per-instance idempotence.

The three workbench icons are already present under `resources/icons`; `InitGui` now fails closed if that directory or any required workbench icon is absent before registering the workbenches, and registers the icon path before `addWorkbench()`.

## Coordination rules

- Update this file at start/handoff of each implementation slice.
- Do not create another GitHub Actions workflow.
- Do not silently retarget semantic references after topology changes.
- Public FreeCAD commands/task panels/document objects are the acceptance surface; utility-only tests are insufficient.
- Keep compatibility shims only where they do not remain authoritative.

# Agent Guide for `freecad-cloth`

This document is the fast-start guide for a new development, review, or quality-control agent. It is deliberately short: the repository state, tests, issues, and pull requests are the source of truth.

## 1. First 5 minutes in a new session

1. Read `README.md` for the product scope.
2. Read `AGENT_STATUS.md` before changing implementation files. Register non-trivial work before coding.
3. Inspect open issues and pull requests, especially the current milestone issues and any PR that touches your intended area.
4. Check the canonical workflow at `.github/workflows/canonical-execution.yml`; do not create a second workflow for routine validation.
5. Inspect the relevant source/tests before deciding what is missing. Do not reimplement an area merely because an issue description is old.

Repository-level execution policy is defined by the external `ADVANCED_TOOL_MODE.md` contract used by the project tooling. In particular, execution must be inspected, verified, and persisted; non-terminal work is never treated as complete.

## 2. What the project is

`freecad-cloth` is a FreeCAD extension for two connected but separable domains:

- **Cloth Pattern**: parametric 2D sewing-pattern pieces and construction metadata.
- **Cloth Simulation**: meshing, sewing constraints, avatar collision, and deterministic cloth simulation.

The important architectural boundary is **model/geometry/solver code must remain usable without the FreeCAD GUI**. GUI imports should stay lazy and GUI commands should operate on persistent model objects rather than becoming the source of truth.

## 3. Current architecture and source of truth

### Pattern side

The pattern object is the parametric source of truth. Current work includes native recomputable pattern pieces, dimensions, seam allowance/grainline metadata, semantic IDs, and an interactive drafting phase.

Do not make a canvas or task panel the authoritative representation of a pattern. UI edits must update persistent model data and remain correct after recompute/save/reload.

### Simulation side

The simulation is intended to remain solver-neutral. The current deterministic CPU XPBD/PBD implementation is an implementation backend, not the document schema. A future backend adapter should be able to replace the solver without changing stable pattern/seam document metadata.

A reproducible simulation should be derivable from pattern geometry, seam graph, collision/avatar proxy, material parameters, and pins.

### GUI boundary

Pure-Python FreeCAD workbench loading uses `InitGui.py`/`Gui.addWorkbench`. Keep FreeCAD GUI dependencies out of headless geometry/model/solver modules wherever practical.

## 4. Development priorities

The current roadmap is roughly:

1. Stabilize/merge the interactive 2D drafting work and repair any baseline CI regression.
2. Build production seam-allowance geometry, notches, grainline/fold markers, labels, and deterministic SVG/DXF export.
3. Build a robust seam graph and backend adapter for simulation.
4. Add avatar/body collision import and fitting workflow.
5. Add deterministic drape quality gates and performance profiling.

See the corresponding GitHub issues for acceptance criteria; do not infer completion from issue status alone.

## 5. Parallel-agent rules

- **Register before coding.** Use `AGENT_STATUS.md` for non-trivial work.
- **One scope, one owner.** Do not edit another active agent's implementation area unless coordinating or fixing an urgent defect.
- **QC/review is independent.** A QC agent may inspect any area. Prefer comments/review findings over unsolicited implementation changes in an owned area.
- **Do not duplicate the supervisor's work.** If a supervisor task/PR already owns an area, provide evidence, tests, or review findings instead of creating a competing implementation.
- **Keep scope entries current.** Mark work completed or blocked when appropriate.
- **A registry entry, issue, PR, commit, or queued workflow is not proof of completion.** Verify the resulting code and CI state.

## 6. Quality-control checklist

For every meaningful change, check as applicable:

- Headless model/geometry/solver tests pass.
- FreeCAD smoke/load tests pass when `freecadcmd` is available.
- Recompute and save/reload behavior preserves persistent metadata.
- Deterministic operations produce stable results across repeated runs.
- Pins remain fixed; sewing constraints reduce the intended seam gap; no NaN/Inf state is introduced.
- Pattern geometry remains the source of truth after GUI edits.
- GUI imports do not leak into headless modules.
- New features have regression tests for their acceptance criteria.
- Existing public APIs and semantic IDs are not changed casually.
- Documentation describes actual current behavior, not merely planned behavior.

## 7. Pull-request review order

When reviewing an implementation PR:

1. Read the PR description and its referenced issue/acceptance criteria.
2. Inspect the changed-file list and diff.
3. Look for scope overlap with `AGENT_STATUS.md` and other open PRs.
4. Run or inspect the relevant tests and canonical CI result.
5. Check persistence/recompute/headless behavior, not just the GUI happy path.
6. Report concrete defects first, with file/line evidence and a minimal reproduction where possible.
7. Do not merge another agent's PR merely because it looks plausible; merge requires verified checks and repository state.

## 8. Useful current references

- `README.md` — user-facing project overview and current workbench capabilities.
- `AGENT_STATUS.md` — parallel-agent ownership/status registry.
- `.github/workflows/canonical-execution.yml` — canonical CI/execution path.
- GitHub issue #43 — current research/architecture snapshot and milestone roadmap.
- GitHub issue #45 — seam allowance, markers, and SVG/DXF milestone.
- GitHub issue #46 — seam graph and solver-backend-adapter milestone.
- GitHub issue #44 — XPBD regression repair task.
- GitHub PR #41 — interactive 2D pattern drafting implementation currently under review.

## 9. What not to do

- Do not add a parallel CI workflow just to run a test.
- Do not make Blender, Tissu, or another external solver a mandatory FreeCAD dependency.
- Do not store essential pattern semantics only in GUI state.
- Do not replace existing architecture wholesale when an issue asks for an incremental extension.
- Do not claim a task is complete from a queued/in-progress workflow, an agent registry entry, or an issue comment alone.

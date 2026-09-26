# Development and agent guide

## Python runtime baseline

The project-wide Python baseline is **3.12 or newer**. Use Python 3.12 for local development, packaging, tests, and the canonical FreeCAD CI image. This baseline is intentional: current upstream Tissu requires Python >=3.12, so keeping the workbench and optional solver backend on the same interpreter family avoids an unsupported embedded-runtime split.

FreeCAD remains a host-provided runtime for installations, but the supported development/CI FreeCAD environment must itself run Python 3.12 or newer.

## Canonical module architecture

The package tree under `freecad_cloth/` is the authoritative implementation tree.

Only FreeCAD bootstrap/tooling files are kept at repository root: `Init.py`, `InitGui.py`, and the interpreter-level `sitecustomize.py` hook used by the CI environment. Do not add root-level Pattern, Sewing, Avatar, Drape, Simulation, solver, model, GUI, command, or adapter modules.

Use fully qualified package imports in implementation and tests, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`. Historical top-level imports are migrated at their call sites; compatibility shims are not recreated as a substitute.

Workbench ownership is explicit: `pattern`, `sewing`, `avatar`, and `simulation` own their domain implementations; `common` and `shared` contain only genuinely reusable contracts/utilities. Duplicate implementation files across packages are prohibited.

## Non-negotiable CI contract

There is exactly one workflow: `.github/workflows/canonical-execution.yml`.

Public `pull_request` events execute the canonical graph on GitHub-hosted infrastructure only. Untrusted pull-request code is never assigned a self-hosted runner.

Trusted `push`, scheduled, and `workflow_dispatch` runs use one `runner_router` job. It may select an idle `self-hosted/linux/x64/docker` runner only when the optional `CLOTH_RUNNER_DISCOVERY_TOKEN` can list repository runners. Missing credentials, unauthorized/invalid API responses, or no idle matching runner fail closed to `ubuntu-latest`.

The runner-discovery credential is separate from the ordinary `GITHUB_TOKEN` and must never be logged. Do not add `pull_request_target`, a privileged PR broker, a duplicate watchdog, or a second canonical workflow.

Pull-request jobs check out `github.event.pull_request.head.sha`, not an ephemeral merge ref, with persisted checkout credentials disabled.

The canonical FreeCAD test image is Python 3.12-based; a CI run that starts FreeCAD under Python <3.12 is unsupported.

Any UI, workflow, runner, or simulation-facing change must use the canonical workflow as its acceptance path. Never weaken screenshot, geometry, simulation, or artifact assertions to make CI green.

## Required verification

Choose the smallest evidence set that proves the change:

- pure model/core change → focused Python tests;
- FreeCAD document/API change → real FreeCAD smoke test;
- task-panel/UI change → real FreeCAD/Xvfb scenario;
- persistent data change → save/reload test;
- simulation change → deterministic reference-solver regression;
- screenshot-facing change → all canonical screenshot states remain valid;
- backend/dependency change → import the dependency in the same Python 3.12 FreeCAD runtime used by CI.

A passing utility script is not a substitute for public workbench acceptance.

## Agent execution contract

Before changing code: inspect current `main`, open PRs/issues, active release gates, and the canonical workflow. Re-cut implementation branches from current `main`.

Every implementation issue/PR should identify:

- authoritative data model/API;
- allowed files and dependencies;
- focused tests and real-FreeCAD acceptance;
- expected screenshots/artifacts;
- explicit non-goals;
- whether the canonical workflow must remain unchanged.

Use one focused concern per PR. Do not revive stale branches or multiply workflows. Before merge: inspect the diff and changed files, verify terminal-green CI, merge, verify the merge, then delete the source branch.

When an issue is closed, use an explicit GitHub state reason (`completed`, `duplicate`, or `not_planned`) and record the reason in the issue conversation. Do not close an unresolved engineering problem merely to reduce queue size.

## UI/UX contract

Task panels follow **Context → Primary action → Secondary actions → Parameters → Recovery**.

Persistent state belongs in FreeCAD document objects/properties. Selection and previews are transient. Multi-step sewing stages selection before commit; `Enter` completes a stage, `Delete` undoes the latest stage, and `Esc` cancels. Invalid candidates must be visibly rejected.

Simulation presents target validity before Run/Step. `Run` is primary, `Step` is debug/secondary, and `Reset` is recovery. Stale derived state always includes an actionable reason.

## Prototype → MVP → production

**Prototype:** prove native PatternPiece/Sewing/DrapeTarget boundaries, transactional sewing, deterministic arrangement, preview mesh, CPU reference simulation, save/reload and invalidation.

**MVP:** make a repeatable garment workflow with robust semantic references/topology repair, 1:N/M:N/free sewing, arrangement points, mannequin measurements/poses, generic CAD targets, quality/material presets, pinning and production-oriented 2D output.

**Production:** add higher-fidelity replaceable human providers, richer target/subelement selection, fit/stress/strain/pressure diagnostics, grading/nesting/manufacturing validation, advanced construction and optional solver benchmarks.

## Agent state

Keep `AGENT_STATUS.md` and `TOOL_STATE.md` compact. They are the durable coordination records; do not create a new status document for every session.

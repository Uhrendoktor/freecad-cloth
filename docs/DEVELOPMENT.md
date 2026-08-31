# Development and agent guide

## Non-negotiable CI contract

There is exactly one workflow: `.github/workflows/canonical-execution.yml`.

Do not replace, duplicate, or casually refactor it. In particular, preserve the existing Docker/Xvfb path that launches real FreeCAD, captures four 1280×720 PNGs, validates their PNG signature/dimensions/size, and uploads `cloth-gui-screenshots` on `main` pushes. GUI diagnostics remain available as `cloth-gui-diagnostics`.

Any UI or workflow-facing change must use the canonical workflow as its acceptance path. Never weaken screenshot assertions to make CI green.

## Required verification

Choose the smallest evidence set that proves the change:

- pure model/core change → focused Python tests;
- FreeCAD document/API change → real FreeCAD smoke test;
- task-panel/UI change → real FreeCAD/Xvfb scenario;
- persistent data change → save/reload test;
- simulation change → deterministic reference-solver regression;
- screenshot-facing change → all four screenshot states remain valid.

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

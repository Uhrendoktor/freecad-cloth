# Development and agent guide

## Python runtime baseline

The project-wide Python baseline is **3.12 or newer**. Use Python 3.12 for local development, packaging, tests, and the canonical FreeCAD CI image. This baseline is intentional: current upstream Tissu requires Python >=3.12, so keeping the workbench and optional solver backend on the same interpreter family avoids an unsupported embedded-runtime split.

FreeCAD remains a host-provided runtime for installations, but the supported development/CI FreeCAD environment must itself run Python 3.12 or newer.

## Canonical module architecture

The package tree under `freecad_cloth/` is the authoritative implementation tree.

Only FreeCAD bootstrap/tooling files are kept at repository root: `Init.py`, `InitGui.py`, and the interpreter-level `sitecustomize.py` hook used by the CI environment. Do not add root-level Pattern, Sewing, Avatar, Drape, Simulation, solver, model, GUI, command, or adapter modules.

Use fully qualified package imports in implementation and tests, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`. Historical top-level imports are migrated at their call sites; compatibility shims are not recreated as a substitute.

Workbench ownership is explicit: `pattern`, `sewing`, `avatar`, and `simulation` own their domain implementations; `common` and `shared` contain only genuinely reusable contracts/utilities. Duplicate implementation files across packages are prohibited.

## Agent-oriented verification

In addition to the normal lint/test gates, the development environment enforces deterministic safeguards for multi-agent reliability:

- Pyright runs in standard mode for the existing broad core profile and strict mode for selected deterministic core modules.
- Vulture runs at 100% confidence on changed common/shared/tooling files.
- Hypothesis covers deterministic round-trip properties and state-machine invariants for core models.
- CrossHair checks a small, explicitly curated pure-function contract surface.
- Pull-request CI rejects newly introduced Python clones while tolerating legacy duplication.

These checks complement the architecture contracts rather than replacing them. Dynamic FreeCAD GUI/command surfaces remain outside the strict Pyright set until matching host stubs are available.

## Python quality gates

Install the development toolchain with `python -m pip install -e ".[dev]"` and `pre-commit install`. Ruff is the canonical formatter/linter; the same configuration is used locally and in CI. Pyright provides type checking for the headless/core surface, and Import Linter enforces dependency direction.

CI runs the full repository Ruff check and formatter check. Legacy code must not be exempted by adding broad rule suppressions; use a targeted per-file exception only when a host callback or compatibility surface genuinely cannot satisfy a rule.

## Documentation contract

Every module in `freecad_cloth/` and `tools/` has a module docstring. Public domain classes and functions have docstrings that describe behavior rather than repeating their names. Comments explain non-obvious reasons, compatibility constraints or performance trade-offs; they do not replace contract documentation.

## Non-negotiable CI contract

There is exactly one workflow: `.github/workflows/canonical-execution.yml`.

### Runner routing

Pull requests use GitHub-hosted runners directly. They never enter the self-hosted runner path.

Trusted `push`, scheduled, and manual runs are local-first: the canonical workflow starts one `local_runner_readiness` sentinel on the existing `self-hosted/linux/x64/docker` runner. Every substantive job depends on that sentinel, so the fallback cannot race with work that has already started.

A small hosted `runner_watchdog` waits up to 45 seconds for the local sentinel. When the local runner does not start, it dispatches the same canonical workflow in explicit `runner_mode=hosted` mode and cancels the stalled source run. Manual `workflow_dispatch` with `runner_mode=hosted` still forces the hosted path.

There is no `pull_request_target` broker, privileged runner discovery token, second workflow, periodic five-minute validation schedule, or duplicate runner heartbeat. The single daily schedule remains for repository maintenance and runner/fallback coverage.

The canonical FreeCAD image is Python 3.12-based. PR checkouts use the immutable PR head SHA with persisted checkout credentials disabled.

Do not replace, duplicate, or casually refactor this routing. Preserve the existing Docker/Xvfb path that launches real FreeCAD and captures the validated GUI states and artifacts. Any UI, workflow, runner, or simulation-facing change must use the canonical workflow as its acceptance path. Never weaken screenshot, geometry, simulation, or artifact assertions to make CI green.

## Required verification

Choose the smallest evidence set that proves the change:

- pure model/core change → focused Python tests;
- FreeCAD document/API change → real FreeCAD smoke test;
- task-panel/UI change → real FreeCAD/Xvfb scenario;
- persistent data change → save/reload test;
- simulation change → Tissu integration/solver regression and deterministic input-model tests;
- screenshot-facing change → all canonical screenshot states remain valid;
- backend/dependency change → import the dependency in the same Python 3.12 FreeCAD runtime used by CI.

A passing utility script is not a substitute for public workbench acceptance.

## Agent execution contract

Before changing code, verify the target branch HEAD and read only the canonical documentation relevant to the requested change. Inspect a governing issue/PR only when its number is known or the task is explicitly about its work.

Do not enumerate the repository's entire issue/PR history. Do not ingest all open issues or PRs because they are linked from a task. Closed issues, merged PRs, old branches, historical runs and artifact archives are not current context.

When a task depends on a live coordination issue, use the current issue body as the coordination summary and inspect child issues only for the specific hypothesis being tested. Do not treat historical child-issue prose as implementation authority.

Re-cut implementation branches from the current target HEAD. Before merge: inspect the diff and changed files, verify terminal-green CI for the exact head, merge, verify the merge, then delete the source branch when permitted.

When an issue is closed, use an explicit GitHub state reason (`completed`, `duplicate`, or `not_planned`) and record the reason in the issue conversation. Do not close an unresolved engineering problem merely to reduce queue size.

## Task prompt contract

For non-trivial agent work, use the seven-field prompt contract in the root `AGENTS.md`. That file is the canonical prompt schema; this document defines the execution behavior around it.

Keep prompts bounded, omit historical conversations and large logs, and give links or identifiers so the agent can inspect only the relevant evidence.

## UI/UX contract

Task panels follow **Context → Primary action → Secondary actions → Parameters → Recovery**.

Persistent state belongs in FreeCAD document objects/properties. Selection and previews are transient. Multi-step sewing stages selection before commit; `Enter` completes a stage, `Delete` undoes the latest stage, and `Esc` cancels. Invalid candidates must be visibly rejected.

Simulation presents target validity before Run/Step. `Run` is primary, `Step` is debug/secondary, and `Reset` is recovery. Stale derived state always includes an actionable reason.

## Prototype → MVP → production

**Prototype:** prove native PatternPiece/Sewing/DrapeTarget boundaries, transactional sewing, deterministic arrangement, preview mesh, Tissu simulation, save/reload and invalidation.

**MVP:** make a repeatable garment workflow with robust semantic references/topology repair, 1:N/M:N/free sewing, arrangement points, mannequin measurements/poses, generic CAD targets, quality/material presets, pinning and production-oriented 2D output.

**Production:** add higher-fidelity replaceable human providers, richer target/subelement selection, fit/stress/strain/pressure diagnostics, grading/nesting/manufacturing validation, advanced construction and optional solver benchmarks.

## Agent state

Keep `AGENT_STATUS.md` and `TOOL_STATE.md` compact. They are current-state summaries, not historical experiment logs.

## Simulation review evidence

Simulation changes are governed by [SIMULATION_REVIEW.md](SIMULATION_REVIEW.md) and the current coordination ledger named in `AGENT_STATUS.md`. Actual rendered screenshots are the primary human-review evidence; logs, metrics and artifact archives are secondary.

A simulation change is not considered visually reviewed until a human records what the rendered geometry does and the screenshots correspond to the exact commit under discussion. Fork PRs do not receive write credentials for evidence publication; contributors must attach the rendered evidence manually in the governing PR/issue.

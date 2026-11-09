# Development guide

This guide covers human development and validation workflows. AI-agent execution, task-prompt, and state-file guidance lives in [Agent workflow guidelines](../agents/WORKFLOW_GUIDELINES.md); the root [`AGENTS.md`](../../AGENTS.md) remains authoritative.

## Python runtime baseline

The project-wide Python baseline is **3.12 or newer**. Use Python 3.12 for local development, packaging, tests, and the canonical FreeCAD CI image. This baseline is intentional: current upstream PositionBasedDynamics requires Python >=3.12, so keeping the workbench and optional solver backend on the same interpreter family avoids an unsupported embedded-runtime split.

FreeCAD remains a host-provided runtime for installations, but the supported development/CI FreeCAD environment must itself run Python 3.12 or newer.

## Canonical module architecture

The package tree under `freecad_cloth/` is the authoritative implementation tree.

Only FreeCAD bootstrap/tooling files are kept at repository root: `Init.py`, `InitGui.py`, and the interpreter-level `sitecustomize.py` hook used by the CI environment. The hook contains only CI/Qt compatibility behavior and must not mutate production runtime classes. Do not add root-level Pattern, Sewing, Avatar, Drape, Simulation, solver, model, GUI, command, or adapter modules.

Use fully qualified package imports in implementation and tests, for example `freecad_cloth.pattern.PatternCommands`, `freecad_cloth.sewing.SewingNetworkCommands`, and `freecad_cloth.simulation.DrapeTarget`. Historical top-level imports are migrated at their call sites; compatibility shims are not recreated as a substitute.

Workbench ownership is explicit: `pattern`, `sewing`, `avatar`, and `simulation` own their domain implementations; `common` is infrastructure only; `shared` contains host/domain-neutral immutable contracts. Domain adapters belong with their owning domain. Duplicate implementation files and compatibility-only architectural namespaces are prohibited.

## Automated quality and verification gates

The canonical quality gate applies the same strict policies to the complete tracked Python repository.

- Ruff runs formatting and **all rules plus preview** across every tracked `.py` and `.pyi` file. Only the rules documented as incompatible with Ruff's formatter may be ignored. Per-file ignores, test-only rule exemptions, inline `noqa`, and legacy baselines are prohibited.
- Pyright includes the repository root and uses global `strict` mode for production code, GUI/command adapters, loaders, tests, fixtures, bootstrap files, and CI tooling. There is one configuration, with no file allowlist or excluded source paths. Missing imports, missing module sources, missing stubs, and import cycles are blocking diagnostics.
- The Python documentation contract checks every tracked source and stub. Google-style docstrings explain module/class/function behavior, parameter semantics, return/yield values, and explicit failure conditions rather than relying on placeholder prose.
- Vulture checks high-confidence unused production code; Hypothesis exercises generated geometry, numeric invariants, and state-machine behavior; CrossHair explores selected pure contracts.
- Import Linter enforces package dependency direction. ast-grep and the source-rewriting policy enforce project-specific architectural and runtime constraints not expressed by Ruff or Pyright.
- Pull-request CI rejects newly introduced Python clones across production code, tests, and CI tooling. Artifact-budget and visual-provenance gates protect published evidence.

These tools complement executable acceptance coverage; static analysis does not replace real FreeCAD document, Sketcher, GUI, persistence, or simulation tests.

## Python quality gates

Install the development toolchain with `python -m pip install -e ".[dev]"` and `pre-commit install`. Ruff is the canonical formatter/linter. The same full rule selection and preview policy applies locally and in CI.

Pyright's `include: ["."]` and `typeCheckingMode: "strict"` are intentional. Do not narrow the include list to selected production files, move files out of scope, disable missing-import diagnostics, or replace global strictness with a per-file strict list. At native FreeCAD/Qt boundaries, add accurate type stubs and structural protocols rather than suppressing unresolved imports or weakening the project profile.

Ruff's `ALL` selection covers correctness, security, import hygiene, annotations, complexity, documentation, and test code. The formatter-conflict ignore list is documented in `pyproject.toml`; all other findings must be repaired in source. Do not add per-file ignores, `noqa`, blanket casts, or weakened test assertions to make the gate green.

## Documentation contract

`tools/check_documentation_contract.py` runs over the entire tracked Python inventory and is also a pre-commit gate. Every module, class, function, method, nested helper, private helper, and test requires a descriptive docstring. Google-style `Args` entries describe all parameters other than conventional `self`/`cls`; `Returns` and `Yields` explain non-None results; and `Raises` documents explicit exception conditions. Documentation must be accurate, substantive, and free of suppression comments.

## Non-negotiable CI contract

There is exactly one workflow: `.github/workflows/canonical-execution.yml`.

### Runner routing

All validation, publication, artifact-budget, maintenance, and merge-queue jobs use the existing `self-hosted/linux/x64/docker` runner. GitHub-hosted runners and automatic hosted fallback are disabled; this repository's CI does not consume Microsoft-hosted runner minutes.

Pull-request jobs run locally only when the head branch belongs to this repository and the PR author is not Dependabot. Fork-originated and Dependabot PRs are skipped rather than executing untrusted code on the persistent machine. Manual dispatch, scheduled validation, trusted pushes, and merge-queue validation use the same local runner. Merge-group readiness checks the associated PR heads and authors and fails closed for external or Dependabot code.

The `local_runner_readiness` sentinel verifies Docker before substantive work begins. Static Python tools use a dependency-keyed virtual environment under `RUNNER_TOOL_CACHE/freecad-cloth/venvs`; it is recreated only when the Python version, `pyproject.toml`, or explicit extra requirements change. FreeCAD evidence validators use a separate persistent environment. The PBD image action checks the local Docker daemon first, then pulls the immutable GHCR tag, and builds only when neither cache contains it. Installed packages and Docker images persist across workflow runs.


There is no `pull_request_target` broker, privileged runner discovery token, second workflow, periodic five-minute validation schedule, or duplicate runner heartbeat. The daily schedule remains for repository maintenance and static validation.

The canonical FreeCAD image is Python 3.12-based. PR checkouts use the immutable PR head SHA with persisted checkout credentials disabled.

Do not replace, duplicate, or casually refactor this routing. Preserve the existing Docker/Xvfb path that launches real FreeCAD and captures the validated GUI states and artifacts. Any UI, workflow, runner, or simulation-facing change must use the canonical workflow as its acceptance path. Never weaken screenshot, geometry, simulation, or artifact assertions to make CI green.

## Tool and test inventories

[Tool inventory](TOOL_INVENTORY.md) lists the maintained repository tools. [Test inventory](TEST_INVENTORY.md) explains the execution groups; the authoritative per-module routing lives in `tools/ci/python_validation.py`, which fails when a pytest module is missing or duplicated.

## Required verification

Choose the smallest evidence set that proves the change:

- pure model/core change → focused Python tests;
- FreeCAD document/API change → real FreeCAD smoke test;
- task-panel/UI change → real FreeCAD/Xvfb scenario;
- persistent data change → save/reload test;
- simulation change → PositionBasedDynamics integration/solver regression and deterministic input-model tests;
- screenshot-facing change → all canonical screenshot states remain valid;
- backend/dependency change → import the dependency in the same Python 3.12 FreeCAD runtime used by CI.

A passing utility script is not a substitute for public workbench acceptance.

## UI/UX contract

Task panels follow **Context → Primary action → Secondary actions → Parameters → Recovery**.

Persistent state belongs in FreeCAD document objects/properties. Selection and previews are transient. Multi-step sewing stages selection before commit; `Enter` completes a stage, `Delete` undoes the latest stage, and `Esc` cancels. Invalid candidates must be visibly rejected.

Simulation presents target validity before Run/Step. `Run` is primary, `Step` is debug/secondary, and `Reset` is recovery. Stale derived state always includes an actionable reason.

## Prototype → MVP → production

**Prototype:** prove native PatternPiece/Sewing/DrapeTarget boundaries, transactional sewing, deterministic arrangement, preview mesh, PositionBasedDynamics simulation, save/reload and invalidation.

**MVP:** make a repeatable garment workflow with robust semantic references/topology repair, 1:N/M:N/free sewing, arrangement points, mannequin measurements/poses, generic CAD targets, quality/material presets, pinning and production-oriented 2D output.

**Production:** add higher-fidelity replaceable human providers, richer target/subelement selection, fit/stress/strain/pressure diagnostics, grading/nesting/manufacturing validation, advanced construction and optional solver benchmarks.

## Simulation review evidence

Simulation changes are governed by [SIMULATION_REVIEW.md](SIMULATION_REVIEW.md) and the current coordination ledger named in `AGENT_STATUS.md`. Actual rendered screenshots are the primary human-review evidence; logs, metrics and artifact archives are secondary.

A simulation change is not considered visually reviewed until a human records what the rendered geometry does and the screenshots correspond to the exact commit under discussion. Fork PRs do not receive write credentials for evidence publication; contributors must attach the rendered evidence manually in the governing PR/issue.
## CI runtime and performance

The canonical workflow is intentionally parallel: runner readiness and the PositionBasedDynamics validation image fan out into the acceptance jobs. Keep this dependency shape intact when refactoring; reducing runner count by serializing acceptance jobs usually increases wall-clock time.

Runtime rules:

- Run Ruff format checks and lint read-only over every tracked Python file on every quality-gate invocation; the workflow must report style errors rather than silently rewriting the checkout.
- Pull immutable, content-derived CI images only when they are not already present on a warm self-hosted runner. Hosted runners will naturally take the pull path.
- The PBD image build publishes the image; downstream jobs are responsible for pulling it. The builder does not perform a second verification pull because that would duplicate the network transfer on an otherwise disposable runner.
- Superseded workflow runs are cancelled whenever their triggering ref is not `refs/heads/main`; main runs, including the push produced by a merged PR, are never cancelled by concurrency.
- Use GitHub-hosted dependency caching where supported. The static Python gate caches its pip download cache using pyproject.toml as the dependency key.
- Prefer independent jobs for expensive GUI/simulation checks. Combine work only when the combined execution demonstrably reduces runtime without sacrificing isolation or acceptance coverage.

The critical path is normally dominated by the slowest visual/simulation job after the readiness/image prerequisites, followed by the publication job. Changes that reduce repeated image transfers, package installation, or unnecessary setup are preferred before more invasive parallelism changes.

### Canonical CI structure

The repository intentionally has one event-driven workflow, `.github/workflows/canonical-execution.yml`. It coordinates jobs and acceptance dependencies; it does not own Docker lifecycle code.

CI implementation is split into three reusable composite actions:

- `.github/actions/freecad-container/action.yml` owns the container boundary and common environment.
- `.github/actions/freecad-test/action.yml` owns canonical checkout, bounded FreeCAD launch, optional preflight/validation, and evidence upload.
- `.github/actions/publish-visual-evidence/action.yml` owns the main-branch and PR evidence publication paths.

Long shell/Python logic belongs under `tools/ci/`. The important contracts are explicit and testable there: FreeCAD process startup/termination, acceptance validation, simulation manifest validation, visual freshness/provenance, runner fallback, and maintenance cleanup.

Equivalent GUI cases use a matrix. Expensive visual and simulation cases remain separate jobs so they can run in parallel on hosted runners. Combining those cases into one job would reduce runner setup duplication but increase wall-clock time.

### Runtime budget

Every FreeCAD application invocation is hard-capped at 120 seconds. The surrounding container action is capped at 130 seconds, leaving a small termination/diagnostic margin. Timeouts are intentional: an acceptance or screenshot task that cannot complete inside this budget is treated as a performance regression rather than allowed to hang.

The 120-second budget applies to FreeCAD acceptance, screenshot, turntable, and simulation invocations. Registry image pulls are infrastructure operations and use one bounded 180-second transfer instead of restarting partial downloads at 60-second intervals; this keeps cold-cache CI reliable without extending the FreeCAD execution budget.

The immutable PBD image contains the Python packages required by the FreeCAD acceptance suite, avoiding per-test package installation. Self-hosted runners reuse an already-present immutable image and only pull it on a cache miss.

### Workflow quality gates

Pre-commit and canonical CI enforce Ruff, Python architecture/dead-code contracts, actionlint, zizmor, yamllint, and the repository-specific CI structure contract. External Actions in the workflow and local composite Actions are pinned to full commit SHAs and maintained by Dependabot.


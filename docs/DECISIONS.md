# Architecture decisions

This is the durable decision log. It records choices that should remain true after the current task is forgotten. It is not a status log, experiment log, or roadmap.

## D-0001 — Python remains the application language

Date: 2026-10-03  
Status: accepted

Decision: Keep the external FreeCAD workbench, document adapters, GUI, persistence model and domain orchestration in Python.

Why: FreeCAD's external-workbench guidance requires external workbenches to be Python-based, while internal workbenches can mix Python and C++. The application already has a clean boundary between FreeCAD integration, garment semantics and the native simulation backend.

Consequences: Native acceleration belongs behind explicit backend/adapter boundaries. Performance changes start with profiling and Python-side algorithm/data-structure improvements.

Reference: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Workbench_creation.md

## D-0002 — Tissu is the sole production runtime solver

Date: 2026-10-03  
Status: accepted

Decision: Tissu is the only runtime cloth solver. The workbench does not expose a solver registry or a user-selectable fallback physics engine.

Why: Tissu is already a native XPBD cloth SDK with cloth constraints, stitches and mesh collision. Blender's cloth architecture likewise exposes one cloth simulation authority plus cache/bake state rather than a runtime choice among interchangeable solvers.

Consequences: ClothBackend.py contains only the small adapter contract. ClothSolver.py contains only the headless solver-input model used to assemble Tissu input. It must not grow into a second physics engine.

References: Blender Cloth Modifier https://docs.blender.org/manual/en/5.2/modeling/modifiers/physics/cloth.html ; Blender Cloth Dynamics https://docs.blender.org/manual/en/5.2/modeling/geometry_nodes/simulation/cloth_dynamics.html ; Tissu https://github.com/evanrock520-ciencias/Tissu

## D-0003 — Rust is a future acceleration boundary

Date: 2026-10-03  
Status: accepted

Decision: Do not add Rust to the workbench until profiling identifies a bounded hotspot that remains material after algorithm and data-structure optimization. A future Rust module may expose a narrow PyO3 extension built with maturin and implement the existing ClothSimulationBackend contract.

Consequences: Rust must not become a second pattern model, document system, GUI architecture or persistence layer. The Tissu path remains the production solver until a replacement is benchmarked against the same contract.

## D-0004 — Ruff + pre-commit is the Python hygiene baseline

Date: 2026-10-03  
Status: accepted

Decision: Use pinned Ruff for linting/formatting and pre-commit for local enforcement. CI runs Ruff and the formatter as hard gates.

Consequences: One tool owns formatting/import sorting and the selected lint rules. Do not add Black/isort/Flake8 in parallel without a documented architectural reason.

Reference: https://docs.astral.sh/ruff/integrations/

## D-0005 — Documentation is an enforced API contract

Date: 2026-10-03  
Status: accepted

Decision: Python modules and public domain APIs must document their contract close to the implementation. An AST contract checker enforces this independently of style linting.

Documentation should explain behavior, important invariants, side effects, exceptions and lifecycle restrictions. Comments are reserved for non-obvious reasons and compatibility constraints.

Reference: https://peps.python.org/pep-0257/

## D-0006 — Persistent agent knowledge has explicit homes

Date: 2026-10-03  
Status: accepted

Decision: Keep each kind of agent knowledge in one canonical location:
- AGENTS.md: short repository instructions and context firewall.
- docs/ARCHITECTURE.md: invariants, authority, lifecycle and dependency direction.
- docs/DECISIONS.md: durable architectural choices and rationale.
- AGENT_STATUS.md / TOOL_STATE.md: current state.
- .agent/PLANS.md: bounded task execution plans.
- GitHub issue/PR: task-local evidence, experiments and review discussion.

Operational rule: prefer one authoritative location per fact and link to it instead of copying the same claim into multiple status/proposal files.

# FreeCAD Cloth documentation

This directory is the canonical human-facing documentation. Use the existing guides rather than creating parallel wiki pages.

## First-run path

1. **[INSTALLATION.md](INSTALLATION.md)** — prerequisites, user installation, the first-run smoke test, and recovery.
2. **[EXAMPLES.md](EXAMPLES.md)** — the validated Blanket over Cube smoke test, then the tunic workflow.
3. **[USER_GUIDE.md](USER_GUIDE.md)** — the normal Pattern → Sewing → Arrange/Fit → Simulate workflow and common recovery.
4. **[WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md)** — command names, task-panel details, persistence and invalidation behavior.
5. **[RELEASE_GATES.md](RELEASE_GATES.md)** — what is validated for the current release.
6. **[ARCHITECTURE.md](ARCHITECTURE.md)** — authoritative data and dependency contracts.
7. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** — canonical package/module tree and FreeCAD bootstrap layout.
8. **[ROADMAP.md](../ROADMAP.md)** — prototype → MVP → production scope and future work.
9. **[RESEARCH.md](RESEARCH.md)** — condensed garment-workflow research and FreeCAD mapping.
10. **[DEVELOPMENT.md](DEVELOPMENT.md)** — testing, CI, screenshots and contribution guidance.

## Source of truth

- README.md is the project-level orientation.
- docs/INSTALLATION.md, docs/USER_GUIDE.md, docs/WORKBENCH_GUIDE.md, and docs/EXAMPLES.md are the human usage sources of truth.
- docs/RELEASE_GATES.md is the source of truth for the current release boundary and validation meaning of "complete".
- docs/PROJECT_STRUCTURE.md is the source of truth for where implementation modules belong.
- docs/ARCHITECTURE.md is the source of truth for domain ownership and dependency direction.
- docs/ROADMAP.md is the source of truth for future scope.
- docs/ contains durable guidance, not dated scratch notes.

## Documentation rule

Prefer updating an existing canonical document over adding a new note. Dated audit material belongs in the relevant issue/PR or compact supervisor state, not as another permanent document. A new wiki-style page is warranted only when the requirement cannot be satisfied by these guides.

## Workbench model

    Cloth Pattern → Cloth Sewing → Cloth Simulation
           │              │              │
           └──── semantic document model ────┘
                             │
                        solver-neutral
                         derived state

The project aims for a CLO-like garment workflow while remaining FreeCAD-native: Sketcher/Part owns editable geometry, Cloth owns garment semantics, and the solver owns physics. The human mannequin and arbitrary FreeCAD geometry are interchangeable providers of the DrapeTarget contract.

## Release boundary

The current package is 0.1.0. The P0 end-to-end workflow is the validated release-closeout scenario; the current simulation UI includes Pinning mode control and the canonical tunic uses Pinning mode = None. Advanced commercial garment-suite capabilities remain roadmap work and are not implied by a green tunic example.

## Module model

All implementation code lives under freecad_cloth/. Root Init.py and InitGui.py are FreeCAD bootstrap adapters, and root sitecustomize.py is an interpreter/CI hook. Root-level domain modules and compatibility copies are not part of the supported architecture.

- USER_GUIDE.md — human-facing workflow from first run through seams, materials, simulation and recovery.

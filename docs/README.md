# FreeCAD Cloth documentation

This directory is intentionally small. Prefer these canonical documents over a separate wiki.

## Human quickstart

Read these in order when using FreeCAD Cloth:

1. **[INSTALLATION.md](INSTALLATION.md)** — prerequisites, installation into FreeCAD's user `Mod` directory, first launch, and installation recovery.
2. **[USER_GUIDE.md](USER_GUIDE.md)** — the first successful Blanket over Cube run, then the Pattern → Sewing → Arrange/Fit → Simulate garment workflow and recovery.
3. **[EXAMPLES.md](EXAMPLES.md)** — the basic blanket and advanced tunic examples, including where their executable fixtures and visual evidence are generated.
4. **[WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md)** — exact workbench behavior, public commands, seam inspection, fitting, simulation controls, and invalid-state recovery.

For project scope rather than human usage, see [ROADMAP.md](../ROADMAP.md) and [RELEASE_GATES.md](RELEASE_GATES.md).

## Source of truth

- `README.md` is the project-level orientation.
- `docs/INSTALLATION.md`, `docs/USER_GUIDE.md`, `docs/WORKBENCH_GUIDE.md`, and `docs/EXAMPLES.md` are the canonical human-facing usage surface.
- `docs/ARCHITECTURE.md` is the source of truth for data ownership, dependency direction, and invalidation.
- `docs/PROJECT_STRUCTURE.md` is the source of truth for the package/module layout.
- `AGENT_STATUS.md` and `TOOL_STATE.md` are coordination records, not user guides.
- Dated audits and scratch notes belong in issues/PRs rather than new permanent documentation.

## Workbench model

```text
Cloth Pattern → Cloth Sewing → Cloth Simulation
       │              │              │
       └──── semantic document model ────┘
                         │
                    solver-neutral
                     derived state
```

The project remains FreeCAD-native: Sketcher/Part own editable geometry, Cloth owns garment semantics, and the solver owns derived physics state. A human mannequin and supported generic FreeCAD Shape/PartDesign/Body/Mesh geometry are providers of the same persistent `DrapeTarget` contract.

## Where examples and visual evidence live

The executable example drivers live in `tests/`, including:

- `tests/freecad_visual_examples.py` for the basic Blanket over Cube fixture.
- `tests/freecad_garment_e2e_smoke.py` for the broader garment/tunic workflow.

The canonical GitHub Actions workflow writes generated visual evidence under `docs/images/generated/` while the visual jobs run. The stable README-facing assets are published separately to the `docs/screenshots` branch and are referenced by the root README. Treat generated files as validation artifacts; do not hand-edit them and present the result as a test.

## Developer/contributor pointer

Development, CI, screenshots, and contribution mechanics are documented separately in [DEVELOPMENT.md](DEVELOPMENT.md). That document is intentionally not part of the human quickstart.

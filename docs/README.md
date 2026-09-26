# FreeCAD Cloth documentation

This directory is intentionally small. Read the documents in this order:

1. **[INSTALLATION.md](INSTALLATION.md)** — install the workbench and verify the first run.
2. **[EXAMPLES.md](EXAMPLES.md)** — run the **Blanket over Cube** smoke test, then the tunic acceptance example.
3. **[USER_GUIDE.md](USER_GUIDE.md)** — the canonical human workflow from pattern through recovery and tunic.
4. **WORKBENCH_GUIDE.md** — detailed workflow, public commands and UI behavior.
5. **ARCHITECTURE.md** — authoritative data, dependency and invalidation contracts.
6. **PROJECT_STRUCTURE.md** — canonical package/module tree and FreeCAD bootstrap layout.
7. **[ROADMAP.md](../ROADMAP.md)** — prototype → MVP → production scope and release gates.
8. **RESEARCH.md** — condensed CLO/garment-workflow research and FreeCAD mapping.
9. **DEVELOPMENT.md** — testing, CI, screenshots, agent handoff and contribution rules.

## Source of truth

- `README.md` is the project-level orientation.
- `AGENT_STATUS.md` is the current machine-readable supervisor/release record.
- `TOOL_STATE.md` is the compact execution-policy/state record.
- `docs/PROJECT_STRUCTURE.md` is the source of truth for where implementation modules belong.
- `docs/ARCHITECTURE.md` is the source of truth for domain ownership and dependency direction.
- `docs/USER_GUIDE.md` is the canonical first-run human workflow.
- `docs/` contains durable guidance, not dated scratch notes.

## Documentation rule

Prefer updating an existing canonical document over adding a new note. Dated audit material belongs in the relevant issue/PR or in the compact supervisor state, not as another permanent document. If a new document is genuinely necessary, link it here and explain why it cannot fit an existing contract.

## Workbench model

```text
Cloth Pattern → Cloth Sewing → Cloth Simulation
       │              │              │
       └──── semantic document model ────┘
                         │
                    solver-neutral
                     derived state
```

The project aims for a CLO-like garment workflow while remaining FreeCAD-native: Sketcher/Part own editable geometry, Cloth owns garment semantics, and the solver owns physics. The human mannequin and arbitrary FreeCAD geometry are interchangeable providers of one `DrapeTarget` contract.

## Module model

All implementation code lives under `freecad_cloth/`. Root `Init.py` and `InitGui.py` are FreeCAD bootstrap adapters, and root `sitecustomize.py` is an interpreter/CI hook. Root-level domain modules and compatibility copies are not part of the supported architecture.

- `USER_GUIDE.md` — human-facing workflow from first run through seams, materials, simulation and recovery.

# FreeCAD Cloth documentation

This directory is intentionally small. Read only the document relevant to the task; do not load the whole directory by default.

## Source of truth

- `README.md` — project-level human orientation.
- `AGENTS.md` — portable agent contract and context firewall.
- `AGENT_STATUS.md` — current machine-readable supervisor/release record.
- `TOOL_STATE.md` — compact execution-policy/state record.
- `docs/PROJECT_STRUCTURE.md` — source of truth for implementation module placement.
- `docs/ARCHITECTURE.md` — source of truth for domain ownership and dependency direction.
- `docs/ROADMAP.md` — durable roadmap; not live status.
- `docs/RESEARCH.md` — design research; not live status.
- `docs/DEVELOPMENT.md` — testing, CI, screenshots and contribution rules.
- `freecad/freecad_cloth/` — modern FreeCAD loader adapters; not a second implementation tree.

## Context policy

Current state comes from the current branch/HEAD plus the two compact state files. Issue/PR history is task-local evidence, not repository-wide context. Closed issues, old branches, old runs and old artifacts are historical unless the task explicitly requests historical reconstruction.

Prefer updating an existing canonical document over creating another status/proposal note. Dated evidence belongs in its governing issue/PR. Keep permanent docs focused on durable contracts.

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

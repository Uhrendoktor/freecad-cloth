# FreeCAD Cloth documentation

This directory is intentionally small. Read the documents in this order:

1. **WORKBENCH_GUIDE.md** — user workflow and UI behavior.
2. **ARCHITECTURE.md** — authoritative data, dependency and invalidation contracts.
3. **ROADMAP.md** — prototype → MVP → production scope and release gates.
4. **RESEARCH.md** — condensed CLO/garment-workflow research and FreeCAD mapping.
5. **DEVELOPMENT.md** — testing, CI, screenshots, agent handoff and contribution rules.

## Source of truth

- `README.md` is the project-level orientation.
- `AGENT_STATUS.md` is the current machine-readable supervisor/release record.
- `TOOL_STATE.md` is the compact execution-policy/state record.
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

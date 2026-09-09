# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main at cleanup start: `86eea3e33518dc82048d44677331d93407a0fe89`
- Structure migration PR: #408 (merged)
- Module-tree cleanup: in progress
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root Python files: `Init.py`, `InitGui.py`, and interpreter-level `sitecustomize.py` only
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Package structure

```
freecad_cloth/
├── avatar/        — Avatar model, collision, arrangement, fitting, commands, GUI
├── common/        — Shared utilities and document adapters
├── pattern/       — Pattern geometry, IR, mesh, objects, schema, sketch, sync, OCCT, derived geometry, commands, GUI
├── sewing/        — Sewing graph, references, assembly, constraints, correspondence, commands, GUI, network, objects, plan, semantics, view
├── simulation/    — Simulation backend, commands, GUI, mesh quality, objects, quality, drape, target, stale guard, XPBD, diagnostics
├── shared/        — Shared target/collision contracts
└── gui.py         — ClothWorkbenchBase shared base class
```

Implementation modules belong under this package tree. `Init.py` and `InitGui.py` remain at repository root because FreeCAD discovers those bootstrap files in a directly installed `Mod` directory. Root `sitecustomize.py` is an interpreter/CI hook, not Cloth domain implementation.

## Release gates

- P0: canonical end-to-end garment fixture — #155, #278.
- P0: DrapeTarget-authoritative acceptance — #284.
- P0: native Sketcher acceptance/topology repair — #298, #297.
- P0: simulation quality/material lifecycle — #145.
- P1: sewing completion — #275.
- P1: pattern production parity — #162, #360.
- Later: production avatar fidelity #374; diagnostics/manufacturing #362; optional solver benchmark #148; P2 backend evaluation #404.

## Architecture / UX

`Sketcher → PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; solver owns physics. Human mannequin and generic FreeCAD geometry are providers of one target-neutral DrapeTarget contract.

Task panels use Context → Primary action → Secondary actions → Parameters → Recovery. Stale state exposes a reason and recovery action. Sewing retains explicit staged interactions and Simulation retains Run/Step/Reset recovery.

## Structure migration

The package tree is the canonical implementation architecture. There are no root-level Pattern/Sewing/Avatar/Drape/Simulation implementation modules and no root compatibility shims. Internal callers and tests use fully qualified `freecad_cloth.<package>.<module>` imports. `Init.py` and `InitGui.py` are bootstrap adapters only.

The target-neutral `DrapeTarget` implementation lives in `freecad_cloth.simulation.DrapeTarget`; duplicate copies in `freecad_cloth.pattern` are removed. Common diagnostics have one owner under `freecad_cloth.common`.

## Agent rules

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches when tooling permits. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

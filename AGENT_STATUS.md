# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main after structure audit: `c3c0d42d093bbcfb585ef8782860f180bfb3f4fc`
- Structure migration PR: #408 (merged)
- Module-tree cleanup: fitting command ownership consolidated under `freecad_cloth/avatar/FittingCommands.py`; duplicate simulation copy removed
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

- P0: canonical end-to-end garment fixture — #155, #278. The acceptance bar remains 3+ native Sketcher-backed pieces, curved sewing, save/reload, invalidation, deterministic re-simulation, and real FreeCAD/Xvfb evidence.
- P0: DrapeTarget-authoritative acceptance — #284. Core lifecycle acceptance is completed; continue guarding against regressions in target invalidation/cache correctness.
- P0: native Sketcher acceptance/topology repair — #298, #297. #298 is completed by PR #422; retain the acceptance tests as regression gates.
- P0: simulation quality/material lifecycle — #145. Quality/material persistence and status controls are implemented; terminal canonical GUI acceptance remains the release evidence gate.
- P1: sewing completion — #275.
- P1: pattern production parity — #162, #360.
- Later: production avatar fidelity #374; diagnostics/manufacturing #362; optional solver benchmark #148; P2 backend evaluation #404.

## Active focused work

- Audit found PR #433's provider-specific MakeHuman `ready` exception masks a stale collision-source lifecycle on the historical sampled-avatar path. Do not use provider-specific readiness exceptions to bypass target invalidation.
- Audit hardened `DrapeTarget` source signatures to hash complete mesh topology instead of aggregate counts/bounds/sums, while retaining `hashCode()` only for lightweight test doubles.

## Architecture / UX

`Sketcher → PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; solver owns physics. Human mannequin and generic FreeCAD geometry are providers of one target-neutral DrapeTarget contract.

Task panels use Context → Primary action → Secondary actions → Parameters → Recovery. Stale state exposes a reason and recovery action. Sewing retains explicit staged interactions and Simulation retains Run/Step/Reset recovery.

## Structure migration

The package tree is the canonical implementation architecture. There are no root-level Pattern/Sewing/Avatar/Drape/Simulation implementation modules and no root compatibility shims. Internal callers and tests use fully qualified `freecad_cloth.<package>.<module>` imports. `Init.py` and `InitGui.py` are bootstrap adapters only.

Fitting commands are owned by `freecad_cloth.avatar.FittingCommands`; `freecad_cloth.simulation` owns simulation/drape implementation. There is one fitting command implementation and one common diagnostics implementation. `DrapeTarget` remains authoritative for collision-target lifecycle.

## Agent rules

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches when tooling permits. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

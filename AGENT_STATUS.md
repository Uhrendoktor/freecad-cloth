# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `e721190` (package structure migration complete)
- Structure migration PR: #408 (merged)
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root entry points: `Init.py` (marker), `InitGui.py` (FreeCAD GUI registration)
- Canonical CI: `.github/workflows/canonical-execution.yml`
- Open PRs: 0
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Package structure

```
freecad_cloth/
├── avatar/        — Avatar model, collision, arrangement, fitting, commands, GUI
├── common/        — Shared utilities (CommandAdapter, ClothDiagnostics)
├── pattern/       — Pattern geometry, IR, mesh, objects, schema, sketch, sync, OCCT, derived geometry, commands, GUI
├── sewing/        — Sewing graph, references, assembly, constraints, correspondence, commands, GUI, network, objects, plan, semantics, view
├── simulation/    — Simulation backend, commands, GUI, mesh quality, objects, quality, scene, stale guard, XPBD, drake
├── shared/        — Shared targets (collision surface, drape target reference)
└── gui.py         — ClothWorkbenchBase shared base class
```

All root-level modules have been moved into their respective `freecad_cloth/` subpackages with updated imports. Root `Init.py` and `InitGui.py` remain as FreeCAD entry points for backwards-compatible installation directly into a Mod directory.

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

## Prototype → MVP → Production

Prototype proves native semantic boundaries and end-to-end invalidation. MVP makes sewing, fitting, mannequin, generic target, material/quality and production-2D workflows repeatable. Production adds higher-fidelity avatars, richer diagnostics/targets, grading/nesting/manufacturing and advanced construction without changing public contracts.

## Structure migration

The standard `pyproject.toml` package boundary under `freecad_cloth/` is now complete. All root-level modules have been moved into their respective subpackages (`avatar`, `pattern`, `sewing`, `simulation`, `common`) with updated imports preserved. Root `Init.py` and `InitGui.py` remain as FreeCAD entry points for backwards-compatible installation directly into a Mod directory. Package submodules own Pattern, Sewing and Simulation workbench registration. All imports have been updated to fully-qualified paths (`freecad_cloth.{package}.{module}`).

## Agent rules

Import surface audit complete — all `tests/*.py` paths corrected to `freecad_cloth.*` qualified imports. Root compatibility shims retained at `Init.py`, `InitGui.py`, and top-level `Pattern*.py / Sewing*.py`. CI canonical workflow unchanged. 315 tests collected, 277 passed, 37 failed (assertions against runtime state).

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches when tooling permits. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

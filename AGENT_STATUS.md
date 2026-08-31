# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `03cd25f54bf2c7a0301329030cbc2bc4992b8942`
- Structure migration PR: #408 (merged)
- Reversible pre-change snapshot: `backup/pre-structure-20260831` (branch; tag creation is not exposed by the available GitHub connector)
- Canonical CI: `.github/workflows/canonical-execution.yml`
- Open PRs: 0
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

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

The standard `pyproject.toml` package boundary under `freecad_cloth/` is now merged. Root `Init.py`/`InitGui.py` and legacy top-level modules remain intact. Package submodules own Pattern, Sewing and Simulation workbench registration. Compatibility shims remain until later migration slices are proven by canonical FreeCAD/Xvfb acceptance.

## Agent rules

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches when tooling permits. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

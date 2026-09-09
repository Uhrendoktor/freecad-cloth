# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Main baseline for active branches: `344d84fc8d4150a67b9e4a5ed7683728af23d801`
- Structure migration PR: #408 (merged)
- Module-tree cleanup: in progress
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root Python files: `Init.py`, `InitGui.py`, and interpreter-level `sitecustomize.py` only
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Release gates

- P0: canonical end-to-end garment fixture — #155, #278.
- P0: DrapeTarget-authoritative acceptance — #284.
- P0: native Sketcher acceptance/topology repair — #298, #297.
- P0: simulation quality/material lifecycle — #145.
- P1: sewing completion — #275.
- P1: pattern production parity — #162, #360.
- Later: production avatar fidelity #374; diagnostics/manufacturing #362; optional solver benchmark #148; P2 backend evaluation #404.

## Active focused work

- #298 native Sketcher GUI/XvFB acceptance on `agent/issue-298-sketcher-acceptance-20260909`; reuses the canonical workflow and adds no second CI workflow.
- #145 simulation quality/material persistence acceptance on `agent/issue-145-quality-persistence-20260909`; intentionally uses the same canonical workflow when promoted into the GUI runner.

## Architecture / UX

`Sketcher → PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; solver owns physics. Human mannequin and generic FreeCAD geometry are providers of one target-neutral DrapeTarget contract.

Task panels use Context → Primary action → Secondary actions → Parameters → Recovery. Stale state exposes a reason and recovery action. Sewing retains explicit staged interactions and Simulation retains Run/Step/Reset recovery.

## Structure migration

The package tree is the canonical implementation architecture. There are no root-level Pattern/Sewing/Avatar/Drape/Simulation implementation modules and no root compatibility shims. Internal callers and tests use fully qualified `freecad_cloth.<package>.<module>` imports. `Init.py` and `InitGui.py` are bootstrap adapters only.

The target-neutral `DrapeTarget` implementation lives in `freecad_cloth.simulation.DrapeTarget`; duplicate copies in `freecad_cloth.pattern` are removed. Common diagnostics have one owner under `freecad_cloth.common`.

## Agent rules

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches when tooling permits. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.
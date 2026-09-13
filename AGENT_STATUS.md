# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `61984f921c4f19b72d9488d1e18f2cabe629921c` (merged PR #452)
- Recent merged implementation: PR #450 six-side tunic drape audit; PR #452 avoids redundant GUI drape-target refresh during the screenshot fixture
- Module-tree cleanup: fitting command ownership consolidated under `freecad_cloth/avatar/FittingCommands.py`; duplicate simulation copy removed
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root Python files: `Init.py`, `InitGui.py`, and interpreter-level `sitecustomize.py` only
- Canonical CI: ` .github/workflows/canonical-execution.yml`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Package structure

```
freecad_cloth/
├── avatar/        — Avatar model, collision, arrangement, fitting, commands, GUI
├── common/        — Shared utilities and document adapters
├── pattern/       — Pattern geometry, IR, mesh, objects, schema, sketch, sync, OCCT, derived geometry, commands, GUI
├── sewing/        — Sewing graph, references, assembly, constraints, correspondence, commands, views, GUI, network, objects, plan, semantics
├── simulation/    — Simulation backend, commands, GUI, mesh quality, objects, quality, drape, target, stale guard, XPBD, diagnostics
├── shared/        — Shared target/collision contracts
└── gui.py         — ClothWorkbenchBase shared base class
```

## Release gates

- P0: canonical end-to-end garment fixture — #155, #278. Acceptance remains 3+ native Sketcher-backed pieces, curved sewing, save/reload, invalidation, deterministic re-simulation, and real FreeCAD/Xvfb evidence.
- P0: DrapeTarget-authoritative acceptance — #284. Continue guarding target invalidation/cache correctness.
- P0: native Sketcher acceptance/topology repair — #298, #297. #298 completed by PR #422; retain acceptance tests as regression gates.
- P0: simulation quality/material lifecycle — #145. Quality/material persistence and status controls are implemented; terminal canonical GUI acceptance remains the release evidence gate.
- P1: sewing completion — #275.
- P1: pattern production parity — #162, #360.
- Later: production avatar fidelity #374; diagnostics/manufacturing #362; optional solver benchmark #148; P2 backend evaluation #404.

## Active focused work

- Keep DrapeTarget source signatures topology-sensitive; use complete mesh topology where available and `hashCode()` only for lightweight test doubles.
- Do not add provider-specific readiness exceptions that bypass target invalidation.
- PR #438 remains diagnostic-only and must not be merged.

## Architecture / UX

`Sketcher → PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; solver owns physics. Human mannequin and generic FreeCAD geometry are providers of one target-neutral DrapeTarget contract.

Task panels use Context → Primary action → Secondary actions → Parameters → Recovery. Stale state exposes a reason and recovery action. Sewing retains explicit staged interactions and Simulation retains Run/Step/Reset recovery.

## Agent rules

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches when tooling permits. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

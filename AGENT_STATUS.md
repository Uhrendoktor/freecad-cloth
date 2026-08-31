# Agent status

Machine-readable supervisor/release record. Keep this file compact; durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main at audit start: `cbe6b4ceeaa6af49df7c9e9067e4af6caca1ae11`
- Canonical CI: `.github/workflows/canonical-execution.yml`
- Open PRs at latest audit: `0`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Release gates

- P0: stale DrapeTarget safety — #322, #289, #284.
- P0: canonical end-to-end garment fixture — #155, #278.
- P0: native Sketcher acceptance/topology repair — #298, #297.
- P0: simulation quality/material lifecycle — #145.
- P1: sewing completion — #275.
- P1: pattern production parity — #162, #360.
- Later: production avatar fidelity #374; diagnostics/manufacturing #362; optional solver benchmark #148.

Completed recent slices include native mannequin acceptance (#369), generic FreeCAD-object DrapeTarget (#228, merged #389), arrangement foundation (#385), native Sketcher-first authoring (#383), and command-side stale-target gating (#393). #289 remains open for the deeper document-recompute guard.

## Architecture / UX

`Sketcher → PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; solver owns physics. Human mannequin and generic FreeCAD geometry are providers of one DrapeTarget contract.

Task panels: Context → Primary action → Secondary actions → Parameters → Recovery. Sewing stages before commit (`Enter` complete, `Delete` undo latest stage, `Esc` cancel). Simulation: Run primary, Step debug, Reset recovery. Stale state exposes a reason and recovery action.

## Prototype → MVP → Production

Prototype proves the native semantic boundaries and end-to-end invalidation. MVP makes sewing, fitting, mannequin, generic target, material/quality and production-2D workflows repeatable. Production adds higher-fidelity avatars, richer diagnostics/targets, grading/nesting/manufacturing and advanced construction without changing the public contracts.

## Agent rules

Re-cut implementation branches from current `main`; one focused concern per PR; inspect diffs and terminal-green CI before merge; merge then verify and delete source branches. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

## Documentation

Canonical docs: `docs/README.md`, `docs/WORKBENCH_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/RESEARCH.md`, `docs/DEVELOPMENT.md`. Avoid creating dated duplicate notes.

# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `57b02085e7898977047d25fbcee21a88a3d3ec8b` (supervisor integration: structured drape visual metrics).
- Recent merged work: avatar face-winding correction (#482), deterministic avatar visual sanity (#483), mesh validation/proximity metrics, backend/library evaluation documents.
- Open implementation PRs requiring supervisor gates: #469 (HM08 avatar topology sanity), #453 (collision-surface cache; do not merge until visual evidence is release-quality), #438 (diagnostic-only; must not merge).
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root Python files: `Init.py`, `InitGui.py`, and interpreter-level `sitecustomize.py` only
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Supervisor epic / milestones

- Epic: #471 — release-grade CLO-style garment workflow hardening.
- M0 — baseline / unblock visual truth: #472 plus #484/#501 for solver-neutral drape metrics (keep #484 as the active metric task).
- M1 — release vertical slice: #473, #474.
- M2 — production parity foundations: #475, #476.
- M3 — fit/analysis layer: #477.
- M4 — evidence-led scale/performance: #478.

## Release gates

- P0 end-to-end garment fixture: #143, #155, #278; reused by #473 rather than duplicated.
- P0 DrapeTarget-authoritative acceptance: #284.
- P0 native Sketcher acceptance/topology repair: #297, #298.
- P0 simulation quality/material lifecycle: #145; execution focus is #474.
- P1 sewing completion/correspondence: #275; execution focus is #475.
- P1 pattern production parity: #162, #360; export execution focus is #476.
- Later: production avatar fidelity #374; diagnostics/manufacturing #362; optional backend evaluation is consolidated in #479 (Tissu + PositionBasedDynamics). Duplicate backend issues #148/#404 are closed/superseded.

## Active focused work

- Keep DrapeTarget source signatures topology-sensitive; use complete mesh topology where available and `hashCode()` only for lightweight test doubles.
- Do not add provider-specific readiness exceptions that bypass target invalidation.
- Treat CI-green screenshot capture as necessary but insufficient: visual validity must show a sane avatar and a convincingly worn garment (#472).
- Canonical GUI acceptance now emits `drape-visual-metrics.json` with deterministic bounds, centroid, span ratios, finite-state and target-proximity evidence. Do not turn these observations into hard pass/fail thresholds until baseline measurements are reviewed.
- `trimesh` remains optional/lazy; CPU reference remains correctness baseline.
- Tissu remains sandbox-only until runtime compatibility, constraint/collision parity, determinism, visual parity and performance are demonstrated.
- Do not merge #438.
- Re-cut implementation branches from current `main`; one focused concern per PR.

## Architecture / UX

`Sketcher → PatternPiece → PatternIR/SewingGraph → SimulationScene/DrapeTarget → derived solver state`.

FreeCAD owns geometry/document state; Cloth owns garment semantics; solver owns physics. Human mannequin and generic FreeCAD geometry are providers of one target-neutral DrapeTarget contract.

Task panels use Context → Primary action → Secondary actions → Parameters → Recovery. Stale state exposes a reason and recovery action. Sewing retains explicit staged interactions and Simulation retains Run/Step/Reset recovery.

## Research posture

CLO comparison is a workflow benchmark, not a cloning target. High-value observed concepts include explicit Free/M:N sewing, property-editor-driven simulation controls, particle distance as a mesh-quality/performance control, arrangement points/bounding volumes for fitting, and fit/stress/strain/pressure diagnostics. These concepts map to existing Cloth semantic contracts rather than proprietary internals.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal status, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

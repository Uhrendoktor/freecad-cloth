# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `7217a2d00e513d4e988b8bb98169a5630b66f328` (product state from merged PR #598 plus docs-only supervisor state synchronization).
- Latest merged work: PR #598 passed canonical run #2087 (`35580478353`) with both Python/non-GUI and Full tunic visual/simulation audit jobs green; artifact `10629862765` was directly reviewed across all six drape views plus metrics/manifest/log.
- Open implementation PRs requiring supervisor gates: none after closing duplicate PR #597; #472 remains the active M0 release gate.
- PR #453 was closed without merge because its validated screenshots remained collapsed/edge-on or not production-ready.
- PR #438 remains diagnostic-only and must not merge.
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root Python files: `Init.py`, `InitGui.py`, and interpreter-level `sitecustomize.py` only
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Supervisor epic / milestones

- Epic: #471 — release-grade CLO-style garment workflow hardening.
- M0 — baseline / unblock visual truth: #472; metric implementations #484/#501 are complete and retained as diagnostics.
- M1 — release vertical slice: #473, #474.
- M2 — production parity foundations: #475, #476.
- M3 — fit/analysis layer: #477.
- M4 — evidence-led scale/performance: #478.

## Active focused work

- Keep DrapeTarget source signatures topology-sensitive; use complete mesh topology where available and `hashCode()` only for lightweight test doubles.
- Do not add provider-specific readiness exceptions that bypass target invalidation.
- Treat CI-green screenshot capture as necessary but insufficient: visual validity must show a sane avatar and a convincingly worn garment (#472).
- Canonical GUI acceptance emits `drape-visual-metrics.json` with deterministic bounds, centroid, span ratios, finite-state, target-proximity, connected-component and failure-classification evidence. Post-drape seam correspondence is now recorded diagnostically; do not turn those observations into hard pass/fail thresholds without reviewed baseline evidence.
- `trimesh` remains optional/lazy; CPU reference remains correctness baseline.
- Tissu remains sandbox-only until runtime compatibility, constraint/collision parity, determinism, visual parity and performance are demonstrated.
- Re-cut implementation branches from current `main`; one focused concern per PR.
- Latest verified canonical result: PR #598 head `226fb38f2795450af42c6d2429dddc8c1429627f` passed run #2087 / `35580478353`; artifact `10629862765` was directly inspected. Both drape panels are finite/connected and classified structurally-plausible, while the four seam diagnostics show maximum gaps up to `452.652642 mm`. #472 remains unresolved.
- Fresh supervisor continuation: issue #600 localizes the post-drape seam/target coherence root cause. No fixture A/B churn, solver redesign, collision-model swap, or second workflow.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal status, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

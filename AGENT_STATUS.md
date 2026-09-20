# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `2e1601125b83c55e40fb48d109be4e4b58961f61` (current canonical product state; includes the #553 explicit missing-drape-target diagnostic fix).
- Recent merged work: Python 3.12 / FreeCAD 1.1.0 CI baseline, restored GUI screenshot/GIF export, avatar and simulation turntables, Sketcher-authoritative pattern import, sewing command-surface coverage, simulation-signature regression, MeshValidation disconnected-component fallback, Tissu audit seam mapping, diagnostic drape metrics, LGPL-2.1-or-later project licensing, and triangle-order topology-signature regression coverage.
- Open implementation PRs requiring supervisor gates: none; PR #551 was squash-merged after canonical run #2042 passed both Python/non-GUI and Full tunic visual/simulation audit jobs.
- PR #453 was closed without merge because its validated screenshots remained collapsed/edge-on and not production-ready.
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
- Canonical GUI acceptance emits `drape-visual-metrics.json` with deterministic bounds, centroid, span ratios, finite-state and target-proximity evidence. Do not turn these observations into hard pass/fail thresholds until baseline measurements are reviewed.
- `trimesh` remains optional/lazy; CPU reference remains correctness baseline.
- Tissu remains sandbox-only until runtime compatibility, constraint/collision parity, determinism, visual parity and performance are demonstrated.
- Re-cut implementation branches from current `main`; one focused concern per PR.
- Latest observed canonical result: PR #553 head `6531bfa8da91c987e90811b3b51d0cbadc2a3685` passed canonical run #2043 (`35538717589`) on 2026-09-20; both Python/non-GUI and Full tunic visual/simulation audit jobs passed and `tunic-visual-audit` artifact `10614295587` is retained. The PR was squash-merged to `main` as `2e1601125b83c55e40fb48d109be4e4b58961f61`. Human visual trust for #472 remains unresolved.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal status, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `2c22f0a981a582f3b6c51b61ecda284d7498c2d1` (latest tunic visual-regression runtime bound to 30 solver steps; canonical CI verification still required for commits after the last recorded green run).
- Recent merged work: Python 3.12 / FreeCAD 1.1.0 CI baseline, restored GUI screenshot/GIF export, avatar and simulation turntables, Sketcher-authoritative pattern import, sewing command-surface coverage, simulation-signature regression, and MeshValidation disconnected-component fallback.
- Open implementation PRs requiring supervisor gates: PR #539 (optional Tissu backend and realtime preview), PR #538 (tunic visual validation), PR #536 (diagnostic drape metrics), and PR #535 (canonical validation trigger).
- PR #453 was closed without merge because its validated screenshots remained collapsed/edge-on and not production-ready.
- PR #438 remains diagnostic-only and must not merge.
- Python package boundary: `freecad_cloth/` with `avatar`, `pattern`, `sewing`, `simulation`, `common`, `shared` subpackages
- Root Python files: `Init.py`, `InitGui.py`, and interpreter-level `sitecustomize.py` only
- Canonical CI: `.github/workflows/canonical-execution.yml`
- CI policy: preserve the Docker/Xvfb FreeCAD screenshot/PNG path; never add a second workflow.

## Supervisor epic / milestones

- Epic: #471 — release-grade CLO-style garment workflow hardening.
- M0 — baseline / unblock visual truth: #472 plus active metric implementation #484 (structured drape sanity metrics).
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
- Latest observed canonical results: PR #539 head `178016d43e2aecae7533e61eb9e555cd6c72b285` passed canonical run #1997 (`35097505536`) on 2026-09-16, but the follow-up docs/status branch PR #541 was re-run against the older hard-gate GUI path in canonical run #1998 (`35097812433`) and failed with `RuntimeError: draped panel Drape: Tunic Front rises too far above the shoulder zone: 1484.4 mm` while Python/non-GUI passed. Treat #541 as stale verification evidence; do not merge it as a green-status record. This remains a visual-fixture/metric-gate issue, not a Tissu import failure; coordinate with #536/#538 before changing backend code.

## Agent rules

Inspect → plan → execute → persist → verify. Do not report completion while a required workflow/PR/CI verification is non-terminal. If CI fails, inspect logs/artifacts, repair in scope, rerun, wait for terminal status, and reassess before progressing dependent work. Never weaken tests or multiply workflows. Close issues only with an explicit GitHub state reason and a reason recorded in the conversation.

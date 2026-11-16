# Production PBD throughput profile

## Scope and reproducibility

This report records the exact-head baseline from the dedicated performance follow-up, issue [#2839](https://github.com/Uhrendoktor/freecad-cloth/issues/2839), PR [#2843](https://github.com/Uhrendoktor/freecad-cloth/pull/2843).

Measured run: [GitHub Actions #43867191629, attempt 2](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/43867191629), source commit `a19029006d5d7421ca3641f39441a6e8c4bb8934`, 2026-11-16. This run completed all 30 jobs successfully after the one pattern-export job that initially failed to pull its container image within 180 seconds was retried successfully. Its successful production and preview artifacts are the baseline evidence for the measurements below.

The production and preview workloads are distinct:
- Production is the canonical two-panel tunic audit with its full solver settings and 90 scene steps.
- Fast preview is a separate 120-frame two-panel fixture with one scene substep, one native substep, and one solver iteration. Its cadence is diagnostic and is not a proxy for production throughput.

## Production tunic baseline

The full audit completed 90/90 scene steps and 360 backend-step calls in **24.188 s wall time** and **81.297 s process CPU time**, averaging **3.36 CPU cores**. All seven production acceptance gates passed: finite full-step state, seam overlay, nonempty panels, authoritative seam correspondence, target clearance and penetration, six-view capture, and drape visual diagnostics.

The exact profile was unchanged:
| Setting | Measured value |
|---|---:|
| Cloth particles | 1,958 |
| Collision triangles | 26,756 |
| Collision mode | Mesh |
| Scene substeps | 4 |
| Native pyPBD substeps | 16 |
| Position iterations | 8 |
| Velocity iterations | 8 |
| Scene steps | 90 |
| Backend-step calls | 360 |

Final physical checks:
| Check | Front panel | Back panel |
|---|---:|---:|
| Target clearance | 5.008 mm | 5.005 mm |
| Penetrating vertices | 0 | 0 |
| Seam correspondence gap | multicolumn{2}{c}{0.00 mm maximum} |

Ten motion captures were emitted. The final front and side captures were visually inspected; they showed no gross drape or penetration defect. The numeric acceptance gates remain authoritative.

## Production stage timings

| Stage | Total | Samples | Mean |
|---|---:|---:|---:|
| Native position-constraint projection | 15,222.6 ms | 5,760 | 2.643 ms |
| Native simulation step (inclusive) | 16,504.3 ms | 360 | 45.845 ms |
| Native collision detection | 794 ms | 360 | 2.206 ms |
| Python mesh collision projector | 2,912.3 ms | 360 | 8.090 ms |
| Stitched-pair reconciliation | 1,227.5 ms | 360 | 3.410 ms |

The native `simulation step` timer includes work measured by its nested native timers; do not add its total to the position-projection and collision-detection totals. Position-constraint projection is the dominant measured native stage. Custom mesh projection and stitched-pair reconciliation are also material costs, but they are smaller.

The profile also separates the Python/native bridge, array transfer, GUI event processing, document recompute, seam diagnostics, viewport framing, screenshot capture, and 10-step batch wall/CPU accounting. It checkpoints after completed backend steps so a later timeout does not erase completed stage measurements.

## Runtime and provenance

The baseline ran in the pinned FreeCAD/PBD validation container on a GitHub-hosted CPU runner:
- CPU: AMD EPYC 7763, four CPUs in process affinity/cpuset.
- cgroup CPU quota: unlimited (`cpu.max=max 100000`); no throttled periods or throttled time were recorded.
- CPU pressure during the production sample was low.
- No NVIDIA device/driver was visible; the backend correctly reported CPU execution.
- pyPBD version: 2.2.2. Pinned wheel SHA256: `a5147c9c73e6f51e2963f664e90336a8813a4b37f19c2c20369e5b1ddad59834`.

The preview artifact additionally records the loaded OpenMP libraries `libgomp-870cb1d0.so.1.0.0` and `libgomp.so.1.0.0`. The production profiler is extended to capture the pyPBD module path, loaded OpenMP runtime libraries, and OMP runtime controls on its next exact-head run.

## Preview publication experiment (separate workload)

The Fast-preview transient Coin3D publisher replaces per-vertex updates to the persistent FreeCAD document mesh with bulk coordinate-field updates on transient viewport geometry. Stopping preview restores the persistent publication path.

| Metric | Earlier document-mesh baseline | Transient Coin3D run |
|---|---:|---:|
| Mean state-publication time | 4.465 ms | 0.905 ms |
| Mean callback time | about 7.99 ms | 3.450 ms |
| Preview mesh publication | per-vertex writes to document mesh | 0.162 ms per panel |
| Persistent mesh writes during measured preview | two writes per frame | 0 |

This is a measured publication-path improvement. It does **not** reduce the native production position-constraint projection cost above, and the production audit timing must not be presented as an A/B speedup from this preview-only change.

The preview target remains a measured miss:
- Mean cadence: 18.065 ms (55.36 mean FPS).
- p95 cadence: 20.118 ms.
- Required 60 FPS budget: 16.667 ms for both mean and p95.
- p95 Qt timer wakeup lateness: 14.419 ms; the scheduler already requests its 1 ms minimum interval.

The diagnostic therefore remains explicitly separate and is not represented as a pass. The remaining observed preview-cadence limit is event-loop/timer wakeup rather than mesh publication.

## Engineering decision and remaining work

No solver identity, solver iteration count, scene/native substep count, timestep, particle density, collision mode, authored geometry, collision clearance, seam constraints, penetration checks, or physical acceptance threshold was reduced.

The production audit now runs as a **blocking** 90-step CI gate with its existing 360-second execution allowance. A timeout, partial checkpoint, or failed physical gate fails the follow-up. The Fast-preview cadence benchmark stays diagnostic-only and cannot mask or substitute for production acceptance.

The profiler localizes the dominant production compute stage to native position-constraint projection, but this PR does not claim a native solver speedup. Any further optimization of that native stage needs its own evidence-led implementation experiment and must preserve all settings and physical gates. Issue #2839 remains open until the agreed throughput work and exact-head validation are complete.

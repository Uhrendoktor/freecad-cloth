# Reuse one OpenMP team in native PBD constraint projection

## Goal

Measure whether a single persistent OpenMP team reduces the overhead of native pyPBD position-constraint projection without changing solver ordering, physical behavior, or the default production runtime.

## Design constraints

- Pin PositionBasedDynamics to `10a70bc146a97873dc3c8fef372f5217e010542e`.
- Keep the installed `pyPBD==2.2.2` wheel as the normal runtime; the source-built experiment extension is isolated under `/opt/pypbd-openmp-experiment`.
- Keep the experiment opt-in through `CLOTH_PBD_OPENMP_TEAM_REUSE=1`; mode 0 retains the upstream per-group implementation.
- Preserve conflict-free group order, the strict `groupSize > 64` parallel threshold, static scheduling for eligible groups, synchronization between groups and iterations, and serial particle-solid contact solving.
- Do not change solver defaults, thread count, timestep, substeps, collision configuration, constraints, geometry, or physical/visual acceptance gates.

## Implementation

- The pinned patch adds a Python-only native build option and the opt-in persistent-team projection path.
- The validation image builds the extension separately, records source/patch/binary provenance, and includes both the Dockerfile and experiment patch in its immutable image identity.
- The production audit wrapper loads the extension by absolute path and rejects an accidental import of the installed wheel.
- Four matched production runs (baseline, candidate, baseline, candidate) write profiles; a fail-closed comparator checks completion, all seven gates, identical runtime/build context and production settings, at least 5% median projection improvement, and no production wall-time regression.
- The experiment and comparator have focused regression tests. The normal realtime preview remains a separate diagnostic.

## Measured result

On the exact implementation head `5b4b2a75d73a7e3deb6add7a34134efcaeb4ae37`, full-validation run [#44172920333, attempt 2](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44172920333) completed successfully: 25 jobs passed, 5 conditional jobs were skipped, and none failed. All four production audits completed 90/90 scene steps and 360/360 backend steps, and all seven physical/visual gates passed in each run.

The matched two-repetition comparison passed with no rejection reasons:

- Median native position projection: 13,366.37 ms baseline vs 12,050.67 ms candidate (**9.84% faster**).
- Median full production wall time: 21,306.37 ms baseline vs 19,934.39 ms candidate (**6.44% lower**).

All four profiles used the pinned source-built extension with matching source, patch, and binary provenance. The installed wheel remains the normal runtime, and no production solver settings were changed.

## Integration status

- PR [#2862](https://github.com/Uhrendoktor/freecad-cloth/pull/2862), the read-only production constraint-group profiler, was merged into `main` at `1a01537581fb25467e1b651dfad1ac4d4d8fe16d`.
- PR [#2866](https://github.com/Uhrendoktor/freecad-cloth/pull/2866) has been retargeted to `main`. It is no longer stacked on an open PR.
- The current exact-head full-validation check after this integration/documentation update is the final merge gate. Do not merge unless it completes successfully and the fail-closed production comparison passes.

## Falsifier

Reject the experiment if any audit is incomplete, any physical/visual gate fails, build/runtime contexts differ, median projection improvement is below 5%, or median full-production wall time regresses. Do not compensate by changing solver or physical parameters.

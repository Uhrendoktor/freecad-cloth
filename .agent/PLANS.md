# Reuse one OpenMP team in native PBD constraint projection

## Objective

Benchmark an opt-in pyPBD implementation that reuses one OpenMP team across ordered position-constraint groups and solver iterations. Preserve the pinned solver identity, grouping, threshold, group ordering, per-group synchronization, all production settings, and all physical/visual acceptance gates. Keep the normal installed pyPBD wheel and production runtime path unchanged.

## Baseline evidence

- Parent/profile head: `e7ba923369ee65f633e9fda0097a27708eb4d7c3`.
- Exact baseline run: [#44116135559](https://github.com/uhrendoktor/freecad-cloth/actions/runs/44116135559), all required jobs passed.
- Production profile: 9,624 constraints across 30 groups; 26 groups exceed the strict upstream threshold of 64.
- Native position projection: 11,172.993 ms of 12,370.300 ms native step time, across 5,760 projection samples.
- Canonical workload: 8 position iterations × 16 native substeps × 360 backend steps, or 1,382,400 ordered group visits.
- Pinned upstream source: PositionBasedDynamics `10a70bc146a97873dc3c8fef372f5217e010542e`.

## Architecture

- The existing PyPI `pyPBD==2.2.2` wheel remains installed and is the default module for the normal runtime.
- A second, isolated Python extension is built from the pinned upstream source in the validation image. The experiment selects either upstream per-group regions (mode 0) or persistent team reuse (mode 1) explicitly.
- The candidate keeps static worksharing for groups strictly larger than 64, serial master-thread execution for smaller groups, and a barrier between every group and solver iteration. Particle-solid contact solving remains serial on the master thread.
- The paired baseline and candidate production audits run on the same runner, source-built binary, image, production fixture and settings. Preview measurements remain separate.

## Scope and non-goals

- Pinned upstream patch under `docker/freecad-ci/patches/`.
- Isolated source build in the existing PBD validation image, exact-mode production audit, fail-closed comparator, and focused regression tests.
- No change to the installed wheel, default runtime import path, solver defaults, OpenMP threshold, thread count, iteration count, timestep, substeps, particle spacing, collision settings, constraints, geometry, seam behavior, or acceptance thresholds.
- No preview-FPS optimization and no additional workflow.

## Implementation result

- [x] Add the pinned native patch and Python-only CMake build option; compile the experiment extension separately from the installed wheel.
- [x] Explicitly load the selected experiment extension by absolute path and reject accidental fallback to the installed wheel.
- [x] Capture native module path, source/patch/binary provenance, experiment mode, CPU affinity and OpenMP/runtime context.
- [x] Run two baseline and two candidate 90-step production audits on the same runner and image; preserve final candidate render evidence.
- [x] Compare profiles fail-closed on completion, all seven gates, production settings, group distribution, native provenance and matched runtime context.
- [x] Run exact-head full canonical validation and inspect the final render evidence.

## Final exact-head evidence

PR [#2866](https://github.com/Uhrendoktor/freecad-cloth/pull/2866) head `e2f673e39ad33f80a8fd20486fd414c2c2ec9018` passed [workflow run #44150715330](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44150715330). All required workflow jobs completed successfully, including strict static/architecture/workflow/security checks, Python validation, GUI acceptance, collision ladder, workbench benchmarks and all four production tunic audits.

Artifact `pbd-openmp-team-reuse-comparison` (ID `14359682222`) records four profiles. Every profile:
- loaded `/opt/pypbd-openmp-experiment/pypbd.cpython-312-x86_64-linux-gnu.so`;
- carried matching source SHA `10a70bc146a97873dc3c8fef372f5217e010542e`, patch SHA256 `f5b5cbd54998908ac985a90749a3053ade654c7b1d9e46a4121a3f25fd3cf839`, and binary SHA256 `5ae71a7c11f7806e6c61d61bd3a0bb5b2fa9a4e4c4a335df2595743a72e3f2a3`;
- completed 90/90 scene steps and 360/360 backend steps, with all seven physical/visual gates passing.

Matched comparison (two repetitions per mode):
- Median native position projection: 8,749.84 ms baseline vs 8,224.43 ms candidate (**6.00% faster**; required minimum 5%).
- Median production wall time: 14,979.95 ms baseline vs 14,194.41 ms candidate (**5.24% lower**; no regression).
- Comparator: `acceptance=passed`, no rejection reasons.

The earlier valid run #44145460639 also passed (9.73% projection improvement and 7.55% lower production wall time). The initial invalid run #44137908584 was rejected because it loaded the stock wheel in both modes; the explicit absolute-path loader corrected that provenance failure. No solver identity, production settings, physical acceptance thresholds, geometry or collision settings were changed.

## Current status and handoff

The implementation and exact-head validation for this experiment are complete. PR #2866 intentionally remains draft and stacked on PR #2862; do not merge or promote it independently of that base. PR #2862 is the read-only constraint-group profile on `main`. Maintainer review and the base-PR integration sequence remain outstanding. After #2862 is integrated, retarget/revalidate #2866 against the resulting base before merging. This experiment does not replace the installed pyPBD wheel or change normal production runtime behavior; any product-runtime rollout requires a separately reviewed packaging and compatibility decision.

## Falsifier / stop condition

Reject this scheduling change if paired projection improvement is below 5%, total production wall time regresses, runtime/build contexts differ, any physical gate fails, or a run is partial/timed out. Do not compensate by changing the threshold, group order, thread count, or any solver/physical parameter.

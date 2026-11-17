# Reuse one OpenMP team in native PBD constraint projection

## Objective

Benchmark an opt-in pyPBD implementation that reuses one OpenMP team across ordered position-constraint groups and solver iterations. Preserve the pinned solver identity, grouping, threshold, group ordering, per-group synchronization, all production settings, and all physical/visual acceptance gates. Keep the normal installed pyPBD wheel and production runtime path unchanged.

## Current evidence

- Parent/profile head: `e7ba923369ee65f633e9fda0097a27708eb4d7c3`.
- Exact baseline run: [#2093](https://github.com/uhrendoktor/freecad-cloth/actions/runs/44116135559), all 30 jobs passed.
- Production profile: 9,624 constraints in 30 groups; 26 groups exceed the strict 64 threshold.
- Native position projection: 11,172.993 ms of 12,370.300 ms native step time, across 5,760 projection calls.
- Canonical workload: 8 position iterations × 16 native substeps × 360 backend steps, or 1,382,400 ordered group visits.
- Pinned upstream source: PositionBasedDynamics `10a70bc146a97873dc3c8fef372f5217e010542e`.

## Architecture

- The existing PyPI `pyPBD==2.2.2` wheel remains installed and is the default module for the normal test matrix.
- A second, isolated Python extension is built from the pinned upstream source in the same CI image. It has two runtime modes: upstream per-group regions (default) and the candidate persistent team (explicit environment opt-in).
- The candidate keeps static worksharing for groups strictly larger than 64, serial master-thread execution for smaller groups, and an explicit barrier between every group and solver iteration. Particle-solid contact solving remains serial on the master thread.
- The paired baseline and candidate production audits run on the same runner, same source-built binary, same image, same production fixture and settings. The preview benchmark remains separate.

## Scope

- Pinned upstream patch under `docker/freecad-ci/patches/`.
- Multi-stage PBD validation-image build that creates the isolated experiment extension.
- A/ B production audit sequence in the existing canonical tunic job.
- A profile comparator and focused tests that verify identical settings/runtime context, full-step completion, all seven gates, and measured timing deltas.
- Minimal runtime-profile metadata to identify the experimental mode.

## Non-goals

- No change to the installed wheel, default import path, solver defaults, OpenMP threshold, thread count, iteration count, timestep, substeps, particle spacing, collision settings, constraints, geometry, seam behavior, or acceptance thresholds.
- No preview-FPS optimization.
- No new workflow or parallel validation engine.

## Implementation steps

1. Add the pinned native patch and a Python-only CMake build option, and compile the experiment extension in a separate Docker build stage.
2. Capture the experiment mode in each production profile.
3. Run two baseline and two candidate 90-step production audits on the isolated source-built extension, preserving candidate rendered evidence.
4. Compare the four profiles and reject the experiment unless the candidate median native projection time is at least 5% lower and median total production time does not regress.
5. Run the exact-head full canonical validation matrix; inspect failure logs and all candidate rendered views.

## Verification

- Build-time import smoke test for the source-built experimental module.
- Focused unit tests for valid comparisons and deliberately invalid/tampered profiles.
- Each of the four paired runs must independently complete 90/90 scene steps, 360/360 backend steps, and all seven physical/visual acceptance gates.
- Verify production settings, native group distributions, CPU affinity/model, OpenMP runtime, and all non-experiment thread controls match across the four runs.
- Require >=5% median projection-time reduction and no median wall-time regression.
- Require the full canonical validation workflow to reach terminal success on the exact branch head.

## Falsifier / stop condition

Reject this scheduling change if the paired median projection improvement is below 5%, total production wall time regresses, runtime/build contexts differ, any physical gate fails, or a run is partial/timed out. Do not compensate by changing the threshold, group order, thread count, or any solver/physical parameter.

## Result

Implementation and paired production evidence are pending.

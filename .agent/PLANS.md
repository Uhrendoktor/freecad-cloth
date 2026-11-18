# Reuse one OpenMP team across the native PBD timestep

## Objective

Measure whether one OpenMP team spanning the complete `TimeStepController::step()` substep loop reduces native PBD overhead beyond the current PR #2866 optimization.

## Evidence and hypothesis

- PR [#2866](https://github.com/Uhrendoktor/freecad-cloth/pull/2866) reuses one OpenMP team across ordered constraint groups and solver iterations inside each `positionConstraintProjection()` invocation.
- The pinned upstream timestep calls this projection once per native substep. The production audit performs 16 native substeps for each of 360 backend steps (5,760 projection invocations).
- The earlier thread-count sweep [#2859](https://github.com/Uhrendoktor/freecad-cloth/pull/2859) did not find a thread count that improved production wall time; thread-count tuning remains out of scope.
- Hypothesis: keeping one team alive across integration, position projection, and velocity updates over all 16 native substeps removes additional team lifecycle overhead.
- Strongest alternative: team lifecycle overhead is not material compared with worksharing and barrier costs.

## Design and invariants

- Pin PositionBasedDynamics to `10a70bc146a97873dc3c8fef372f5217e010542e`.
- Baseline: `CLOTH_PBD_OPENMP_TEAM_REUSE=1`, `CLOTH_PBD_OPENMP_STEP_TEAM_REUSE=0` (current PR #2866 behavior).
- Candidate: `CLOTH_PBD_OPENMP_TEAM_REUSE=1`, `CLOTH_PBD_OPENMP_STEP_TEAM_REUSE=1` (one team across the full native substep loop).
- Preserve the exact native integration and velocity-update formulas, the serial behavior when the rigid-body count does not exceed `MIN_PARALLEL_SIZE`, ordered conflict-free groups, `groupSize > 64`, static scheduling, and barriers between groups, iterations, contacts, and solver phases.
- Keep particle-solid position contacts serial on the master thread.
- Preserve one native projection timing sample per substep (5,760 per production audit).
- Keep the source-built extension isolated under `/opt/pypbd-openmp-experiment`; the installed `pyPBD==2.2.2` wheel remains the normal runtime.
- Do not change thread count, solver defaults, timestep, substeps, iterations, constraints, collision settings, geometry, or physical/visual acceptance gates.

## Verification and falsifier

Run four sequential matched production audits (current baseline, full-step candidate, current baseline, full-step candidate). Every run must complete 90/90 scene steps and 360/360 backend steps and pass all seven physical/visual gates. The fail-closed comparator must verify identical source/build/runtime/production settings except for the new full-step mode flag.

Accept only if median native position-projection time improves by at least 5% and median full-production wall time does not regress. Any incomplete audit, failed gate, context mismatch, smaller projection gain, or production wall-time regression rejects the change. Do not compensate by changing physical or numerical settings.

## Integration status

- Current-best baseline is merged PR #2866 at `4a2f2a29ba17652fe7a30712b540f178363ff8bd`.
- This follow-up is tracked in issue [#2870](https://github.com/Uhrendoktor/freecad-cloth/issues/2870).

# Production pyPBD constraint-group profile

## Purpose

The production tunic audit records the native pyPBD constraint-group size
distribution as a read-only diagnostic. The goal is to distinguish a workload
with a few large groups from one with many small groups before proposing
changes to native projection scheduling.

The profile is stored under `native_constraint_groups` in
`artifacts/tunic-audit/production-pbd-profile.json`. It reports total
constraints and groups, minimum/maximum/mean/median/p90/p95 group size, a fixed
size histogram, and the number and fraction of groups and constraints eligible
for OpenMP parallel execution.

## Upstream execution contract

The source snapshot reviewed for the pinned pyPBD 2.2.2 runtime exposes
`SimulationModel.getConstraintGroups()`. The relevant upstream source
references are:

- [OpenMP threshold, `MIN_PARALLEL_SIZE = 64`](https://github.com/InteractiveComputerGraphics/PositionBasedDynamics/blob/10a70bc146a97873dc3c8fef372f5217e010542e/Common/Common.h#L8)
- [Position-constraint projection loops groups in sequence and uses an OpenMP
  loop only when group size is strictly greater than the threshold](https://github.com/InteractiveComputerGraphics/PositionBasedDynamics/blob/10a70bc146a97873dc3c8fef372f5217e010542e/Simulation/TimeStepController.cpp#L251)
- [Constraint-group construction](https://github.com/InteractiveComputerGraphics/PositionBasedDynamics/blob/10a70bc146a97873dc3c8fef372f5217e010542e/Simulation/SimulationModel.cpp#L1033)

The native grouping is built by pyPBD. Cloth reads the resulting groups only
after the first completed native step, when group initialization has occurred.
It does not invoke group initialization itself, reorder constraints, alter the
threshold, or change solver execution.

## Interpretation

A group with exactly 64 constraints is not parallel-eligible; only groups with
more than 64 constraints enter the native OpenMP parallel branch. The profile
therefore includes both group-level counts above/below the native threshold
and the share of all constraints located in groups above the threshold.

This is a scheduling/workload descriptor, not a measurement of per-constraint
arithmetic cost or per-group elapsed time. Interpret it alongside the native
position-projection timer and the unchanged 90-step physical acceptance gates.
No solver optimization or production-default change should be justified by
the histogram alone.

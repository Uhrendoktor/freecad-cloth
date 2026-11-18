# Benchmark parallel exact KDTree query workers in cloth collision projection

## Objective and hypothesis

Measure whether four workers for the batched exact nearest-centroid query reduce production mesh collision projector time. The strongest alternative is that the KDTree batch is too small and scheduling overhead offsets any parallel-query gain.

## Scope and invariant boundaries

- Keep the installed `pyPBD==2.2.2` runtime as normal; use the existing isolated source-built pyPBD validation extension only for the canonical production audit.
- Keep `CLOTH_PBD_OPENMP_TEAM_REUSE=1` in both A/B arms (the merged PR #2866 path).
- Baseline: `CLOTH_PBD_COLLISION_QUERY_WORKERS=1`; candidate: `=4`.
- Apply the variable only to the vectorized particle-batch query in `MeshCollisionProjector.project()`. The stitched-pair scalar midpoint queries remain at `workers=1`.
- Preserve `eps=0.0`, Euclidean metric, candidate count, triangle refinement, collision clearance, candidate triangles, geometry, solver, time step, native substeps/iterations, stitches, pins, and all physical/visual acceptance gates.
- Exact output equivalence between one and four query workers is covered by focused projector tests.
- Record the environment value in every production profile; the comparator allows only that one value to differ.

## Measurement and acceptance

Use the existing canonical workflow and four sequential matched production audits: baseline, candidate, baseline, candidate. Do not add another workflow.

Every audit must complete 90/90 scene steps and 360/360 backend steps and pass all seven existing physical/visual gates. The comparator must require identical runtime/build/runner context, production settings, constraint grouping, and native pyPBD provenance.

Accept only when median `mesh_collision_projector` time improves by at least 10% and median full-production wall time does not regress. The projector timing must contain exactly 360 samples per audit. Any incomplete audit, failed physical/visual gate, context mismatch, sub-threshold improvement, or production wall-time regression rejects the candidate. Do not weaken thresholds or alter physical/numerical settings after seeing results.

## Current implementation

- The worker count is defaulted to one and passed only to the batch `KDTree.query` call.
- Runtime profiling records `CLOTH_PBD_COLLISION_QUERY_WORKERS`.
- The comparison helper reuses the existing fail-closed production-profile validation and compares the isolated projector stage plus total production wall time.
- The source-built pyPBD image and standard installed runtime are unchanged.

## Falsifier

If the measured projector stage does not improve by at least 10%, conclude that parallel exact centroid queries are not a useful optimization at this batch size. Do not extend the worker count to scalar stitch queries or tune other parameters as an unmeasured workaround.

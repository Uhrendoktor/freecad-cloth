# Cache immutable stitch topology during PBD collision reconciliation

## Objective and hypothesis

Measure whether precomputing connected components for the backend's immutable stitch-pair tuple reduces repeated work in position-level collision reconciliation. The strongest alternative is that midpoint exact KDTree queries and vectorized projection dominate the stage, making union-find reconstruction a small fraction of total time.

## Evidence

The rejected four-profile exact KDTree worker audit (#2876, run #44316139423) records a median of approximately 753 ms in `stitched_pair_reconciliation` per 90-step production audit (360 samples). The backend's `self._stitches` is a tuple established at backend construction and remains unchanged, but `project_stitched_pairs()` currently allocates and fills union-find parent/rank arrays, touched sets, and component dictionaries on every call.

The measured KDTree parallelism candidate was slower; this task keeps all midpoint queries serial and exact.

## Design constraints

- Build deterministic, immutable components once from the fixed stitch tuple.
- Preserve the current sorted component/member ordering.
- Validate pair indices when building the topology.
- Keep per-step position/normal validation, pin checks, group eligibility, endpoint spread checks, AABB checks, exact midpoint query (`eps=0.0, workers=1`), signed-plane test, and all projection operations unchanged.
- Keep an uncached baseline path available through `CLOTH_PBD_STITCH_GROUP_CACHE=0`; candidate/default path is `=1`.
- Keep `CLOTH_PBD_OPENMP_TEAM_REUSE=1` fixed in both modes and do not alter any PBD solver or physical settings.
- Reuse the existing canonical workflow and comparator CLI; do not add a second workflow or a separate comparator entrypoint.

## Acceptance

Four sequential matched production runs (uncached, cached, uncached, cached). All must complete 90/90 scene steps and 360/360 backend steps and pass all seven physical/visual gates. The comparator requires matching runner/runtime/native build/solver context apart from the cache toggle and exactly 360 stitch-stage timing samples per run.

Accept only if median `stitched_pair_reconciliation` time improves by at least 10% and median full-production wall time does not regress. Reject on any output/physical mismatch, incomplete audit, context mismatch, sub-threshold stage gain, or total wall-time regression.

## Falsifier

If the cached topology does not pass the registered stage and wall-time gates, keep the simpler uncached implementation. Do not tune KDTree workers, alter midpoint projection, or change solver/physical settings to compensate.

# Roadmap

The release target is a complete, public FreeCAD workflow, not a feature-count clone of CLO.

## Release order

| Stage | Goal | Main work |
|---|---|---|
| P0 | Safe end-to-end garment slice | Pattern → Sewing → Arrange → DrapeTarget → Simulation → Save/Reload → Invalidate → Rebuild |
| P1 | Remaining repeatable garment-CAD work | richer curved authoring, explicit semantic repair/remap, richer fitting controls, multi-size foundations, expanded production validation |
| Production | Manufacturing + fidelity | higher-fidelity avatar provider, richer targets, diagnostics, grading/nesting/validation, advanced construction, optional solver backends |

## P0 release-closeout gates — historical baseline

1. Native Sketcher-backed PatternPieces can form a multi-piece garment.
2. Semantic seams persist through recompute/save/reload and never silently retarget invalid topology.
3. Segment/free/1:N/M:N sewing has explicit commit/cancel and direction/correspondence validation.
4. Arrangement is deterministic and independent of solver state.
5. `DrapeTarget` is authoritative; mannequin and generic FreeCAD geometry are interchangeable providers.
6. Simulation has deterministic preview/final quality and material controls, Run/Step/Reset and pinning.
7. Target/pattern/sewing edits produce explicit stale derived state; document recompute remains safe.
8. One canonical FreeCAD/Xvfb scenario proves the public workflow and preserves the four PNG artifacts.

## P1 priorities — REMAINING ENHANCEMENTS

- Richer curved-pattern authoring and clearer topology-repair/remap workflows for semantic edge identities.
- Additional mannequin measurement/pose and fitting controls where the current public workflow is still limited.
- Sewing-assistance and correspondence UX beyond the existing transactional semantic seam model.
- Multi-size/grading foundations and stronger production-pattern validation.
- Expanded fit/quality inspection that consumes existing simulation results without creating a second simulation model.

## Production priorities — FUTURE ENHANCEMENTS

- Replaceable high-fidelity human provider behind the existing `DrapeTarget` contract.
- Multiple collision targets and optional face/subelement targeting.
- Stress, strain, fit/tightness and pressure diagnostics with exportable data.
- Grading review, nesting, plotting and manufacturing validation.
- Pleats/folds, topstitch, buttons/buttonholes/tacks, linings/facings, modular blocks and POM.
- Optional native solver benchmarks only after the semantic/reference-solver contract is stable.

## Explicitly deferred

Cloud collaboration, proprietary project formats, photorealistic rendering, full avatar soft-body/animation simulation and mandatory external solver dependencies are outside the core release path.

## Work sequencing rule

A feature moves from prototype to MVP when it is required for a repeatable garment workflow. It moves to production when it adds manufacturing, diagnostics, fidelity or advanced construction without changing the public Pattern/Sewing/DrapeTarget contracts.

Do not pull a visible CLO feature forward merely because it exists in CLO. Stabilize authority, invalidation, recovery, persistence and public-workbench acceptance first.

## Historical release-closeout note

The P0 release-closeout was completed in September 2026 at a specific merged-main state. Its detailed run IDs, artifact hashes, screenshot dimensions and historical PR references are intentionally not repeated here.

Those historical artifacts remain useful evidence when reconstructing that release event, but they are not current repository state. For current state use `AGENT_STATUS.md`, `TOOL_STATE.md`, and the exact current branch/commit.

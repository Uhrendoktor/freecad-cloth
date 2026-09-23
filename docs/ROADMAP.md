# Roadmap

The release target is a complete, public FreeCAD workflow, not a feature-count clone of CLO.

## Release order

| Stage | Goal | Main work |
|---|---|---|
| P0 | Safe end-to-end garment slice | Pattern → Sewing → Arrange → DrapeTarget → Simulation → Save/Reload → Invalidate → Rebuild |
| P1 | Repeatable garment-CAD workflow | curved authoring, Sketcher constraints, robust semantic repair, 1:N/M:N/free sewing, arrangement points, material/quality lifecycle, production 2D export |
| Production | Manufacturing + fidelity | higher-fidelity avatar provider, richer targets, diagnostics, grading/nesting/validation, advanced construction, optional solver backends |

## P0 release gates — COMPLETE FOR THE RELEASE-CLOSEOUT SCENARIO

1. Native Sketcher-backed PatternPieces can form a multi-piece garment.
2. Semantic seams persist through recompute/save/reload and never silently retarget invalid topology.
3. Segment/free/1:N/M:N sewing has explicit commit/cancel and direction/correspondence validation.
4. Arrangement is deterministic and independent of solver state.
5. `DrapeTarget` is authoritative; mannequin and generic FreeCAD geometry are interchangeable providers.
6. Simulation has deterministic preview/final quality and material controls, Run/Step/Reset and pinning.
7. Target/pattern/sewing edits produce explicit stale derived state; document recompute remains safe.
8. One canonical FreeCAD/Xvfb scenario proves the public workflow and preserves the four PNG artifacts.

## P1 priorities — FUTURE ENHANCEMENTS

- Curved pattern authoring through native Sketcher/Part geometry.
- Explicit topology repair/remap UI for semantic edge IDs.
- Transactional Segment, Free, 1:N and M:N sewing with length-aware correspondence.
- Arrangement points, wrap, superimpose and reset.
- Parametric mannequin measurements and basic poses.
- Particle-distance and physical fabric presets.
- Seam allowance, notches, grainline/internal marks, grading foundations and TechDraw/DXF/SVG output.

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

## Current release state

- The P0 release-closeout implementation is present, but the repository is not yet releasable: PR #1075 is the active candidate (exact head `35f5db29d55b0e904b2bacb65e4b2b8446cc1b86`) and exact-head canonical validation has not executed.
- GitHub Actions is currently blocked before job allocation for recent main and release-candidate pushes; zero-job failures do not count as validation.
- The canonical FreeCAD/Xvfb workflow remains the sole workflow. Historical runs prove the workflow graph executes when event delivery works, including real FreeCAD/Xvfb evidence for the 200 mm Blanket-over-Cube fixture.
- Repository hygiene cleanup is implemented by the scheduled maintenance job, but 487 historical remote branches remain because scheduled maintenance is not currently executing.
- The three missing public Sewing command SVG assets were merged in PR #1077; packaging already includes `resources/**/*`. The P1 and Production items listed above are future enhancements rather than active release blockers.

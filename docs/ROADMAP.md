# Roadmap

The release target is a complete, public FreeCAD workflow, not a feature-count clone of CLO.

## Current release order

| Stage | Goal | Main work |
|---|---|---|
| P0 | Safe end-to-end garment slice | Pattern → Sewing → Arrange → DrapeTarget → Simulation → Save/Reload → Invalidate → Rebuild |
| P1 | Repeatable garment-CAD workflow | curved authoring, Sketcher constraints, robust semantic repair, 1:N/M:N/free sewing, arrangement points, material/quality lifecycle, production 2D export |
| Production | Manufacturing + fidelity | higher-fidelity avatar provider, richer targets, diagnostics, grading/nesting/validation, advanced construction, optional solver backends |

## P0 release gates

1. Native Sketcher-backed PatternPieces can form a multi-piece garment.
2. Semantic seams persist through recompute/save/reload and never silently retarget invalid topology.
3. Segment/free/1:N/M:N sewing has explicit commit/cancel and direction/correspondence validation.
4. Arrangement is deterministic and independent of solver state.
5. `DrapeTarget` is authoritative; mannequin and generic FreeCAD geometry are interchangeable providers.
6. Simulation has deterministic preview/final quality and material controls, Run/Step/Reset and pinning.
7. Target/pattern/sewing edits produce explicit stale derived state; document recompute remains safe.
8. One canonical FreeCAD/Xvfb scenario proves the public workflow and preserves the four PNG artifacts.

## P1 priorities

- Curved pattern authoring through native Sketcher/Part geometry.
- Explicit topology repair/remap UI for semantic edge IDs.
- Transactional Segment, Free, 1:N and M:N sewing with length-aware correspondence.
- Arrangement points, wrap, superimpose and reset.
- Parametric mannequin measurements and basic poses.
- Particle-distance and physical fabric presets.
- Seam allowance, notches, grainline/internal marks, grading foundations and TechDraw/DXF/SVG output.

## Production priorities

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

## Current queue

- P0: #322 / #289 / #284 — stale DrapeTarget safety and acceptance.
- P0: #155 / #278 — canonical end-to-end garment fixture.
- P0: #298 / #297 — Sketcher GUI acceptance and topology repair.
- P0: #145 — simulation quality/material lifecycle.
- P1: #275 — sewing completion and correspondence repair UX.
- P1: #162 / #360 — pattern production parity.
- Later: #374 — production avatar fidelity; #362 — diagnostics/manufacturing; #148 — optional solver benchmark.

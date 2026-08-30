# Cloth Workbench release gates

A release is complete only when all gates pass through public FreeCAD workbench workflows.

## Gate A — Pattern

- PatternPiece owns or references native `Sketcher::SketchObject` as authoritative geometry.
- Parametric dimensions/constraints recompute the piece.
- Seam allowance, grainline, notches and internal marks are persistent semantic data.
- Geometry edits invalidate affected seam/mesh/simulation state without silent retargeting.

## Gate B — Sewing

- Segment and free sewing are explicit workflows.
- Curved correspondence supports direction/reversal and mismatch diagnostics.
- 1:N and M:N relationships are persistent and transaction-safe.
- Repair controls operate through the public Sewing task panel.
- Paired seams are inspectable in 2D and 3D.

## Gate C — Fitting / Drape

- Mannequin is a persistent parametric human target.
- Arbitrary FreeCAD Shape/Mesh can be selected as a collision target.
- Arrangement state is persistent and distinct from generic Placement.
- Target geometry and placement changes deterministically invalidate collision/simulation state.

## Gate D — Simulation

- Simulation consumes a target-neutral collision surface.
- Stale targets never make document recompute raise.
- Public Run/Step refuse stale targets with an actionable reason.
- Refresh rebuilds the collision input.
- Fabric properties and particle-distance/quality settings persist.

## Gate E — Canonical acceptance

One scenario must execute through the real workbenches:

`create pattern pieces -> constrain/edit -> sew -> arrange -> select target -> mesh -> simulate -> save/reload -> edit source -> observe invalidation -> refresh -> rebuild -> simulate`

The scenario must run under the canonical FreeCAD/Xvfb workflow and retain diagnostics/screenshots.

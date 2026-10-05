# CLO-style research and feature model

This document is a durable design-research summary, not a current implementation or release-status record. Verify implementation claims against the current branch and current-state records.

## Product boundary

The target is a FreeCAD-native garment workflow with CLO-like interactions, not a clone of proprietary internals.

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD owns editable geometry and document persistence. Cloth owns garment semantics. The solver owns physics. Derived mesh, collision and numerical state are rebuildable.

## Common sewing workflow

Commercial garment tools treat sewing as an explicit, transactional operation rather than an incidental geometry constraint. The useful baseline is:

- Segment Sewing and Free Sewing;
- 1:N, M:1 and M:N relationships;
- selectable ranges on edges/curves;
- explicit orientation/reversal;
- length-aware correspondence diagnostics;
- staged selection with commit/cancel and recovery;
- notches/direction indicators that communicate correspondence;
- persistent seam objects independent of generated mesh topology.

For FreeCAD, these belong in Cloth Sewing. Sketcher constraints remain geometric constraints, not physical seams.

## Pattern-production workflow

A practical garment pattern workflow also needs, in increasing maturity:

- seam allowance with persistent parameters and validation;
- notches and grainlines;
- internal marks, darts, folds and construction annotations;
- measurement-driven dimensions and expressions;
- grading and multi-size review;
- deterministic DXF/SVG/TechDraw output;
- plotting/print layout;
- later nesting and manufacturing validation.

These should be semantic Pattern data and adapters around native FreeCAD geometry, not a second drafting kernel.

## Fitting and simulation workflow

Fitting is more than moving a mesh once. Useful persistent concepts are arrangement points/anchors, wrap direction, superimpose, reset, body measurements and a named collision target. Simulation then adds mesh quality, material parameters, pinning, solver controls and diagnostics.

Particle distance/resolution is a real quality/performance control. Material data should include density/thickness and stretch/shear/bending/friction where the reference solver can use them. Changing these inputs invalidates derived simulation state.

## Avatar strategy

Use one target-neutral interface:

```text
                 DrapeTarget
                /           \
      Human Mannequin     FreeCAD Geometry
      AvatarService        Shape/Body/Mesh
                \           /
                 CollisionSurface
                       |
                   Simulation
```

The deterministic native mannequin is the release baseline for the documented release slice. A higher-fidelity generated/imported human body is a later provider, not a prerequisite and not a new solver path. Current implementation status must be taken from the current repository, not this design summary.

## UI/UX model

Every task panel should answer, in order:

1. What am I editing and is it valid?
2. What is the next primary action?
3. What reversible/inspection actions are available?
4. Which persistent parameters can I change?
5. How do I recover from stale or invalid state?

Use Preview → Apply for multi-parameter fitting changes. Keep selection highlights, transient previews and task-panel state separate from persistent document authority.

## Release order

### Prototype
Prove the boundaries with a small multi-piece garment, transactional sewing, deterministic arrangement, one mannequin and one generic target, preview mesh, CPU reference drape, save/reload and invalidation.

### MVP
Harden semantic references/topology repair, curved correspondence, 1:N/M:N/free sewing, arrangement points, mannequin measurements/poses, generic targets, material/quality presets, pinning and production-oriented 2D output.

### Production
Add higher-fidelity avatar providers, richer collision targeting, fit/stress/strain/pressure maps, grading/nesting/manufacturing validation, advanced construction and optional solver benchmarks.

## FreeCAD mapping

| Need | Prefer native FreeCAD | Cloth layer |
|---|---|---|
| Pattern geometry | Sketcher + Part/OCCT | PatternPiece identity/semantics |
| Constraints | Sketcher constraints/Expressions | Measurement helpers |
| Persistence | DocumentObject, Links, Groups, Placement, recompute | Stable semantic references/invalidation |
| Mesh | Mesh/MeshPart | PatternIR/mesh adapter |
| Production pages | TechDraw/Draft | Garment layers/annotations/export orchestration |
| 3D target | Part/PartDesign/Mesh | DrapeTarget provider |
| Physics | deterministic CPU reference first | solver adapter + material/quality contract |

## Research references

Primary references used for workflow decisions:

- CLO Help Center: 3D Sewing, Segment Sewing, Free Sewing, M:N sewing, Particle Distance, Auto Sewing, Auto Fitting, Set Grading.
- FreeCAD documentation/source: Sketcher SketchObject, Sketcher constraints, TechDraw workbench/API.
- Style3D documentation/workflows: curved pattern authoring, sewing, simulation quality and DXF interchange.
- Seamly2D: measurement-driven drafting and size-parametric patterns.
- Optitex and comparable production tools: fit/tension analysis and manufacturing-oriented pattern workflows.

Specific URLs are intentionally kept here rather than repeated across multiple dated research notes. Verify current vendor documentation before treating a feature as a compatibility promise.


## Avatar Pose Mode UI research

The merged FK skeleton should be edited as a pose tool rather than as a list of
Euler-value fields.

- Blender Pose Mode establishes the viewport-first model: click a bone/joint,
  use the gizmo rings for axis-specific rotation, use the trackball for free
  rotation, and use X-Axis Mirror for bilateral posing. Snapping/precision can
  be temporary interaction aids rather than permanent numeric inputs.
  References:
  https://docs.blender.org/manual/en/latest/editors/3dview/display/gizmo.html
  https://docs.blender.org/manual/en/latest/editors/3dview/controls/snapping.html
  https://docs.blender.org/manual/en/latest/editors/3dview/controls/transform/transform_control/precision.html
- CLO 3D's Adjust Avatar Joints uses FK joint adjustment with a Gizmo and a
  dedicated symmetric control. Its workflow also separates direct joint
  manipulation from broader IK workflows.
  Reference:
  https://support.clo3d.com/hc/en-us/articles/360000013808-Adjust-Avatar-Joints
- Marvelous Designer uses a Unified Gizmo for rotate/move operations and exposes
  X-ray avatar joints, supporting a model where the skeleton is directly
  selectable in the 3D view rather than only through a property panel.
  References:
  https://support.marvelousdesigner.com/hc/en-us/articles/47358262924185-Adjust-Avatar-Pose
  https://support.marvelousdesigner.com/hc/en-us/articles/47358262924185
- Style3D adds bilateral skeleton linkage and joint-angle limits. Angle limits are
  a useful future layer for Cloth, but this PR deliberately does not invent
  anatomical limits that are absent from the current skeleton data contract.
  Reference:
  https://help.style3d.com/studio/en/1f8f/39dc
- FreeCAD exposes the Coin3D scene graph and Pivy event callbacks needed to place
  a transient posing overlay without adding another geometry engine.
  The Coin SoTrackballDragger provides three principal-axis bands plus free-form
  trackball rotation and start/motion/finish callbacks.
  References:
  https://reqrefusion.github.io/FreeCAD-Documentation-html/wiki/en/Code_snippets.html
  https://www.coin3d.org/coin/classSoTrackballDragger.html

Cloth UI mapping:
1. The normal avatar editor is for measurements/provider configuration; Pose Mode
   is a dedicated mode for posing.
2. The user selects a named joint from a small anatomical tree or directly on the
   mannequin.
3. The selected joint gets a 3D rotation gizmo; direct dragging is the primary input.
4. Symmetry and 5-degree angle snapping are visible mode toggles.
5. X/Y/Z sliders provide a lower-friction secondary input; exact Euler values are
   behind a collapsed Precision drawer.
6. Presets provide Standing, Sewing and Sitting starting points.
7. Apply/Rebuild and Cancel preserve the existing staged/persistent document
   semantics.
8. IK and anatomical joint-limit authoring remain explicit follow-up work.

This is intentionally a UI layer over the merged `SkeletonPose`/FK data model;
it does not replace the rig or introduce a second pose representation.

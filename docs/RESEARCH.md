# CLO-style research and feature model

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

The current deterministic native mannequin is the release baseline. It should be recognizably human and persist measurements, pose and rebuild state. A normal FreeCAD Shape/PartDesign/Body/Mesh must be selectable without manual conversion. Visual and collision representations may differ, but both providers expose the same target contract.

A higher-fidelity generated/imported human body is a later provider, not a prerequisite and not a new solver path.

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

# FreeCAD integration research

Research date: 2026-08-30

## Sketcher

FreeCAD Sketcher already provides the general-purpose 2D constraint machinery needed for dimensions and geometric relationships. Its Python interface can create `Sketcher::SketchObject` instances, add geometry and add constraints. citeturn1search12turn1search5

Use Sketcher as an editing/constraint adapter:

- pattern semantics remain in `PatternModel`/native pattern objects;
- Sketcher geometry mirrors the authoritative outline;
- constraints can drive editable geometry;
- generated Sketcher indices are not stable sewing IDs;
- a rebuild must preserve semantic IDs where geometry remains equivalent.

This avoids creating a second custom constraint solver while allowing future constraint-rich drafting.

## Part / OCCT

Part/OCCT is the appropriate boundary for exact curves, wires and geometric operations such as seam-allowance offsets. Offset operations must be treated as derived geometry and validated for self-intersections, cusps and invalid topology.

The pattern model must not depend on the topological ordering of OCCT edges. Semantic edge identity should be stored independently and mapped to generated geometry through an explicit provenance layer.

## Mesh / MeshPart

Simulation topology should be generated from authoritative pattern geometry through a deterministic meshing adapter. Mesh density should be controlled by the simulation-quality contract rather than permanently stored as authoritative pattern geometry.

A topology provenance map should retain which generated boundary segments correspond to which semantic pattern edge/range. This is required for sewing, diagnostics and stable re-simulation.

## TechDraw / Draft

TechDraw is a useful production-output boundary: it can create drawings from FreeCAD shape-bearing objects and export SVG, DXF and PDF. DXF output supports R12/R14, while the scripting API exposes page export. citeturn1search0turn1search7turn1search2

TechDraw should therefore be preferred over a custom drawing/export engine when its representation is sufficient. It should not replace the semantic pattern model.

## FreeCAD document model

Recommended object layers:

```text
FreeCAD Document
├── Pattern Piece objects        # authoritative parameters + semantic IDs
│   ├── outline
│   ├── marks
│   ├── grainline
│   └── seam allowance metadata
├── Seam / Sewing objects        # authoritative assembly semantics
├── Fitting Scene                # avatar/collision + arrangement state
├── Simulation Configuration     # quality/material/solver inputs
└── Derived Simulation State     # disposable mesh/particles/diagnostics
```

All persistent objects should use normal FreeCAD properties and recompute/save/reload behavior. The existing project already follows this model. fileciteturn1file0L2-L2

## Integration risks

- OCCT offset failure on highly concave or degenerate contours;
- semantic-ID loss when regenerating geometry;
- Sketcher topology/index changes after edits;
- mesh edge-count mismatch across sewn boundaries;
- DXF unit/scale ambiguity;
- stale simulation caches after pattern or material changes;
- optional native solver ABI/dependency cost.

## Decision

Keep the architecture FreeCAD-native and solver-neutral. Reuse FreeCAD's geometry, constraint and drawing facilities, but keep garment semantics independent from those generated representations.

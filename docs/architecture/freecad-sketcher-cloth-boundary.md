# FreeCAD Sketcher / Cloth Workbench Boundary

## Principle

**FreeCAD owns geometry. Cloth owns meaning. The solver owns physics.**

The intended dependency direction is:

`Sketcher -> PatternPiece -> SewingGraph -> PatternMesh -> Simulation`

Sketcher remains the authoritative 2D pattern authoring system. Cloth adds garment semantics and workflow. The solver consumes a resolved, solver-neutral representation rather than inspecting Sketcher topology directly.

## Responsibilities

### FreeCAD / Sketcher

Use native Sketcher for:

- lines, arcs and B-splines;
- dimensions and geometric constraints;
- symmetry/equality/tangency/coincidence;
- construction geometry;
- expressions and parametric dimensions;
- normal sketch editing and recompute.

Do not implement a second general-purpose 2D geometry or constraint engine in Cloth.

### PatternPiece

`PatternPiece` is the semantic wrapper around a native Sketcher sketch. It owns or references the sketch and adds garment-specific metadata, including:

- piece identity/name;
- semantic grainlines, notches, darts and folds;
- seam allowance information;
- semantic references to boundary geometry.

Sketch geometry remains authoritative; metadata must not silently create a competing representation.

### Sewing

The Sewing workbench owns physical sewing semantics:

- `Seam` / `SewingGroup` objects;
- references to PatternPiece geometry;
- direction/reversal;
- curved parameter correspondence;
- M:N/free sewing relationships;
- future easing/segmented mappings;
- seam visualization and diagnostics.

Sewing must not be encoded as Sketcher constraints.

### PatternIR / adapter

A solver-neutral adapter resolves the FreeCAD document into:

- piece boundary curves and local coordinates;
- material references;
- semantic sewing relationships;
- resolved curve mappings.

This prevents the solver from depending directly on Sketcher object/topology implementation details and permits future solver backends.

### Simulation

Simulation owns mesh generation, material behavior, collisions, draping and solver state. Its output should remain a normal FreeCAD document object/mesh representation where practical.

## Stable references

Raw `EdgeN` references are not sufficient as long-term semantic identities because Sketch edits can alter topology and numbering. Cloth must maintain a stable semantic reference/adapter strategy and explicitly invalidate references when geometry is deleted, split or otherwise cannot be safely resolved. Never silently retarget a seam to unrelated geometry.

## FreeCAD integration

Prefer native facilities:

- document objects, Links, Groups and Properties for persistence;
- FreeCAD dependency/recompute for downstream invalidation;
- Part/OpenCascade for geometric derivation and offsets where appropriate;
- Spreadsheet/Expressions for garment measurements and parametric sizing;
- TechDraw/Draft/native geometry for production 2D output;
- Mesh/FreeCAD view objects for simulation results.

Cloth should add semantics rather than duplicate these systems.

## Target document structure

```text
Garment (App::Part/group)
├── Patterns
│   ├── PatternPiece -> Sketcher::SketchObject
│   └── PatternPiece -> Sketcher::SketchObject
├── Sewing
│   ├── SewingGroup
│   └── Seam(s)
├── Fabric
├── Avatar
└── Simulation
```

Exact object types should follow existing project conventions.

## Dependency and invalidation contract

A typical dependency chain is:

```text
Sketch edit
    |
    v
PatternPiece geometry
    |
    +--> seam reference resolution
    |
    v
PatternIR
    |
    v
mesh
    |
    v
simulation
```

A geometry change must cause deterministic invalidation of affected derived data. Save/reload must preserve semantic relationships and invalid state. Invalid/deleted geometry must be visible to the user and must not silently resolve to a different edge.

## Verification target

The canonical regression workflow should:

1. create multiple PatternPieces using native Sketcher;
2. create curved edges;
3. define a seam in the Sewing workbench;
4. save and reload;
5. verify seam identity and direction;
6. edit a Sketch dimension/curve and recompute;
7. verify downstream invalidation;
8. remesh and simulate;
9. exercise free/M:N sewing;
10. verify deleted or unresolvable geometry is reported safely.

This architecture is intended to complement the active P0 vertical release workflow and pattern-authoring audit, not replace them.

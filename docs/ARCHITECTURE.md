# Architecture

Research/architecture review: 2026-08-30

## Architectural invariant

FreeCAD Cloth has one authoritative semantic model and several derived representations:

```text
Pattern semantics
      │
      ├── Sketcher / Part geometry adapters
      │
      ├── Sewing graph
      │       │
      │       └── fitting / arrangement scene
      │
      └── deterministic simulation-mesh adapter
                  │
                  └── solver backend
                         │
                         └── diagnostics / derived state
```

The pattern model remains authoritative; generated simulation topology is disposable. This is already the project's documented behavior and is retained. fileciteturn1file0L2-L2

## Pattern authoring layer

A pattern piece owns:

- stable piece ID;
- geometric construction data;
- outline/edge semantic IDs;
- seam allowance parameters;
- grainline;
- notches and internal marks;
- optional dimensional/geometric constraints;
- measurement and validation metadata;
- simulation-resolution hint.

Sketcher is an adapter for interactive constrained geometry, not the semantic owner. FreeCAD's Sketcher already supplies dimensional/geometric constraints and a constraint solver. citeturn1search12turn1search5

Part/OCCT supplies exact curves/wires and geometric operations such as offsets. Offset results are derived and must be validated; their generated edge numbering must never become the stable semantic identity.

## Sewing layer

A sewing relationship is a declarative object containing:

```text
piece_a + range_a
piece_b + range_b
orientation/reversal
correspondence policy
stitch group
construction kind
validation state
```

The solver consumes this graph but does not redefine it. This permits 1:1, 1:N, M:N and free sewing without coupling garment semantics to particle/triangle counts.

## Fitting and arrangement layer

A fitting scene contains:

- avatar/collision-surface reference;
- body measurements where available;
- garment piece placements;
- arrangement points or bounding-volume anchors;
- wrap/direction metadata;
- reset/reproducibility state.

Arrangement is not pattern geometry. The same pattern can be placed in multiple fitting scenes.

## Simulation layer

Simulation configuration is persistent input, while particles, triangles, constraints generated from topology and numerical state are derived. The backend adapter should expose:

- quality preset;
- particle distance/resolution;
- material parameters;
- solver iterations/substeps;
- collision thickness/skin offset;
- pin and stitch constraints;
- deterministic seed/state where applicable.

A change to any simulation input invalidates derived state. CLO and Style3D both demonstrate that simulation quality is a meaningful operational control rather than a cosmetic setting. citeturn0search6turn0search5

## Diagnostics model

Diagnostics should be structured records with severity, object/semantic ID, location/range when available, message and remediation hint. Minimum classes:

- pattern geometry invalid;
- seam range invalid;
- seam length/correspondence mismatch;
- missing construction mark;
- arrangement overlap/penetration;
- excessive stretch/tension;
- solver instability;
- stale derived state.

This allows GUI, tests and future export tooling to consume the same diagnostic contract.

## File/persistence model

Native FCStd is the authoritative project container. Persistent FreeCAD properties store semantic inputs and versioned metadata. JSON-like serialization may remain useful for headless core tests, but it must not become a mandatory second project database.

Interchange layers:

- DXF/AAMA/ASTM-oriented 2D production interchange;
- SVG/TechDraw production sheets;
- OBJ/GLB/FBX-class geometry interchange for avatars/presentation;
- optional sidecar metadata when an external format cannot encode sewing semantics.

Style3D's current DXF workflow shows that practical interchange includes units, grading, seam allowance, annotations and curve normalization. citeturn2search1turn2search2

## FreeCAD integration opportunities

### Sketcher — P1

Use native sketch constraints for dimensions, tangency, symmetry and other 2D relationships. Keep a semantic provenance mapping from pattern edges to Sketcher geometry.

### Part / OCCT — P0/P1

Use exact curves and offset operations for deterministic pattern geometry and seam allowance. Add regression coverage for difficult concave/curved cases.

### MeshPart / mesh adapter — P0

Generate solver topology deterministically from the semantic boundary. Preserve boundary provenance so sewing remains independent of generated edge order.

### TechDraw / Draft — P1

Generate production pages and export SVG/DXF/PDF where appropriate. TechDraw's current documentation confirms DXF and SVG export and exposes `TechDraw.writeDXFPage` for scripting. citeturn1search0turn1search2

### Optional native solver — P2

Keep the deterministic CPU backend as the reference. Benchmark an external PBD/XPBD engine only after the same semantic and diagnostics contract is stable.

## Dependency direction

```text
UI / Workbench commands
        ↓
FreeCAD document adapters
        ↓
FreeCAD-independent semantic core
        ↓
geometry / mesh adapters
        ↓
solver backend adapter
        ↓
reference CPU solver OR optional native backend
```

No layer below the semantic core should own garment semantics. No optional solver should leak its constraint representation into persistent garment data.

## Architecture consequences

- Do not use mesh edge indices as persistent sewing IDs.
- Do not make Sketcher topology the sole source of truth.
- Do not store only a rendered 3D garment and attempt to recover 2D patterns from it.
- Do not require CLO/Style3D/Optitex proprietary project formats for core operation.
- Do not make cloud asset management a core persistence dependency.
- Do not replace the reference solver without benchmark evidence.

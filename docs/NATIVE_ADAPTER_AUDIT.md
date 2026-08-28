# Native FreeCAD adapter audit

Supervisor audit: 2026-08-28.

## OCCT seam allowance

`PatternOCCT.native_offset_wire()` is the FreeCAD-facing adapter around OCCT's 2D offset operation. It is intentionally not the semantic source of truth: `PatternModel` keeps the original sewing boundary and stable semantic edge IDs. The adapter is therefore safe to use for generated geometry while semantic metadata remains independent of OCCT topology.

The FreeCAD smoke test contains a deterministic 100 x 60 rectangle / 10 mm offset regression and checks the expected 120 x 80 bounding box. Failure of the native operation is surfaced rather than silently falling back to a different geometry result.

The adapter is kept separate from the core/headless geometry path so FreeCAD GUI dependencies do not leak into unit tests.

## `App.Placement`

FreeCAD document objects already expose `App::PropertyPlacement`. The workbench uses native Placement at the document boundary; no second transform property is required on `PatternPiece` document objects. The smoke test exercises translation and rotation through `App.Placement`.

The semantic pattern model deliberately does not depend on FreeCAD's GUI object model, which keeps serialization and headless tests portable.

## TechDraw / Draft / SVG / DXF export

The existing semantic SVG exporter remains intentionally bespoke. TechDraw is document/page oriented and is not a drop-in replacement for a garment pattern exporter that must preserve sewing-boundary semantics, grainlines, notches, labels, scale and stable semantic IDs. Draft/TechDraw can be added later as presentation/CAD export adapters, but replacing the current exporter solely to use a native API would discard information or require a second semantic mapping layer.

Therefore the current decision is:

- keep semantic SVG generation in `PatternExport.py`;
- preserve units, scale, sewing-vs-cut semantics and stable IDs there;
- expose native FreeCAD geometry through the OCCT adapter where it is authoritative;
- do not introduce a mandatory TechDraw/Draft dependency for the core workbench;
- treat DXF/print-layout export as a future focused adapter with differential fixtures rather than silently changing the existing output contract.

## Meshing

The same boundary-provenance rule applies to future MeshPart/Netgen adapters: generated triangles may be native, but `boundary segment -> mesh boundary provenance` must remain a workbench semantic contract. No native meshing replacement is accepted until that mapping has deterministic regression coverage.

## Optional solver backends

Tissu and PositionBasedDynamics remain optional research candidates. They are not mandatory runtime dependencies because their native build/ABI requirements are unsuitable for a portable first-party FreeCAD workbench dependency at this stage. The in-tree CPU backend remains the deterministic reference.

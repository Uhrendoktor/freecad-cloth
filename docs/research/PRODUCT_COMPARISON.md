# Product behavior comparison

Research date: 2026-08-30

| Product | Observable workflow strengths | Relevance to FreeCAD Cloth |
|---|---|---|
| CLO 3D | Integrated 2D patterning, semantic sewing, avatar fitting, arrangement, fabric/simulation controls, diagnostics and 3D drape. Simulation quality modes include CPU/GPU variants. citeturn0search6 | Primary behavioral reference for the end-to-end 2D→sew→arrange→simulate loop. Do not copy proprietary internals. |
| CLO-SET | Centralized 3D asset/workflow management, versioning, collaboration, tech packs, measurements, BOM/POM and rendering; integrates with CLO project assets. citeturn0search0turn0search1 | Reference for downstream product-data concepts, not a core garment kernel. |
| Style3D | Traditional 2D CAD pattern workflow plus real-time 3D preview; DXF import/export; explicit sewing and simulation quality modes. citeturn2search11turn0search5 | Strong reference for interoperable DXF workflows, authoring loop and simulation controls. |
| Optitex | 2D/3D CAD, virtual sample editing, fabric simulation, colorways/prints, tension map, multi-stitch and configurable avatars. citeturn0search9 | Reference for fit diagnostics, avatar editing and production-oriented pattern workflows. |
| Seamly2D | Open-source parametric patternmaking driven by measurement files; supports standardized multi-size and individual custom-fit measurements. GPLv3+. citeturn0search4turn2search3 | Strong reference for measurement-driven parametric authoring; license means it should remain a reference/interchange target, not an embedded core dependency. |
| FreeCAD Sketcher | Native 2D geometry and constraint solver with dimensional/geometric relationships. Python API can create sketches and constraints. citeturn1search12turn1search5 | Preferred adapter for constraints and precise editing rather than reimplementing a general 2D constraint solver. |
| FreeCAD Part / MeshPart / TechDraw | OCCT-backed geometry, mesh conversion and native drawing/export infrastructure. TechDraw exports SVG/DXF/PDF; DXF supports R12/R14 output. citeturn1search0turn1search7 | Preferred FreeCAD-native integration boundary for offsets, generated simulation topology and production drawing/export. |

## What should not be copied

Do not reproduce proprietary solver architecture, undocumented project schemas, proprietary binary formats, UI layouts, naming, or implementation details. Reproduce observable behavior and define an independent semantic model.

## Feature implications

1. A pattern piece needs persistent construction identity beyond generated geometry indices.
2. Sewing needs ranges, direction and correspondence semantics.
3. Arrangement must be saved separately from pattern geometry.
4. Simulation quality must affect actual solver inputs and invalidate derived state.
5. Diagnostics must be first-class outputs, not log-only messages.
6. Interchange should prioritize established 2D CAD formats while retaining a richer native FreeCAD document as the source of truth.
7. Downstream collaboration/tech-pack concepts are useful P2/P3 references but should not delay a working garment simulation MVP.

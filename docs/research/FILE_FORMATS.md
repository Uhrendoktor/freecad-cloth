# File formats and interoperability

Research date: 2026-08-30

## Native project format

FreeCAD's FCStd document should remain authoritative for FreeCAD Cloth. Pattern parameters, semantic IDs, sewing graph, fitting-scene metadata, material/simulation settings and versioned project metadata belong in native document objects/properties.

Generated meshes, solver particles and other numerical state are derived data and should be safely regenerable.

## 2D CAD interchange

### DXF / AAMA / ASTM

Style3D explicitly describes its DXF interchange as a 2D pattern format carrying AAMA/ASTM information. Its current importer handles units, grading rules, seam allowance, annotations and curve-point normalization; its exporter can include seam allowance, fabric names, notches and other pattern information. citeturn2search1turn2search2

This makes DXF the highest-priority external production/interchange target, but not a complete native semantic model. Export/import tests must preserve piece identity, net sewing line, seam allowance, notches, grainline, grading where supported, and explicit limitations.

### SVG

SVG is useful for visual/printing workflows and can be generated through FreeCAD TechDraw. It should not be treated as a full garment-CAD semantic interchange format because generic SVG does not inherently encode sewing relationships, grading or fabric semantics. FreeCAD TechDraw supports SVG export. citeturn1search7

### Seamly2D formats

Seamly2D uses measurement-driven pattern files and separate measurement concepts for standardized sizes and custom-fit users. The project has documented `.val` and `.vit` as pattern/measurement file-format topics, but the format documentation remains an open documentation issue; therefore FreeCAD Cloth should not claim stable binary compatibility without a dedicated parser test. citeturn2search0turn2search3

### CLO project assets

CLO-SET documents direct upload of CLO/Marvelous Designer project assets including ZPRJ, ZPAC and AVT. These are useful ecosystem references but are proprietary application formats and should not become a native dependency. citeturn0search0

### 3D interchange

For avatars, collision proxies and presentation, generic 3D formats such as OBJ/GLB/FBX are appropriate boundaries. CLO-SET's viewer supports DAE, FBX, GLB and OBJ among its review formats. citeturn0search0

The MVP should prefer simple, well-supported geometry interchange rather than attempting to reproduce a vendor-specific garment project format.

## FreeCAD export opportunities

TechDraw can create pages from drawable FreeCAD objects and export SVG, DXF and PDF. Its DXF exporter supports R12 and R14. The API also exposes `TechDraw.writeDXFPage(page, filename)`. citeturn1search0turn1search2

Recommended export stack:

- P0: deterministic internal/native document persistence;
- P1: DXF pattern export with units/scale and garment metadata sidecar;
- P1: SVG/TechDraw production sheet;
- P2: robust DXF import round-trip;
- P2: avatar/mesh import interoperability;
- P3: vendor-specific project-format research only if a concrete user workflow requires it.

## Interchange principle

Never infer semantic sewing identity from DXF entity order or generated mesh edge numbering. Preserve explicit stable IDs in the native document and use sidecars/annotations where an external format cannot carry the semantics itself. This also avoids the metadata-loss problem observed in open-source SVG/DXF workflows. citeturn2search17

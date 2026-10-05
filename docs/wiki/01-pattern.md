# 01 · Pattern authoring

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Cloth Pattern workbench showing native Sketcher-backed garment geometry" width="900"></p>

## What the feature is

Cloth Pattern is the 2D garment-authoring stage. The important architectural choice is that the editable geometry remains native FreeCAD Sketcher geometry. Cloth adds garment meaning around it instead of introducing a second polygon editor.

A PatternPiece carries a stable semantic identity and points to the authoritative sketch geometry. Pattern metadata can describe seam allowance, grainline, notches and internal marks.

## What a human should see

| Visual check | Expected result |
| --- | --- |
| Garment outline | Closed, legible piece boundary |
| Construction information | Grainline, notches and marks are visibly distinct from the boundary |
| Editing authority | The geometry is clearly the FreeCAD/Sketcher representation |
| Document structure | The garment remains part of a persistent FreeCAD document rather than a detached image or mesh |
| Recompute behavior | Editing the underlying sketch is the path that changes authoritative geometry |

## Pattern workflow

<strong>Create piece → edit native Sketch → add garment metadata → recompute → validate → sew</strong>

## 3D Pattern Pen

The **3D Pattern Pen** is the first 3D-to-2D authoring bridge. Select or create the mannequin/drape target, start the command from **Cloth Pattern → 3D Pattern Pen**, and drag over the visible mannequin surface. Release the mouse to lift the pen; continue with another drag to extend the same boundary. **Finish Stroke → Pattern** creates a normal native Sketcher-backed PatternPiece.

The first implementation deliberately uses a bounded planar projection. Before anything is converted, Cloth measures the maximum distance of the sampled surface boundary from a deterministic local plane. A patch that exceeds the configured **Planar deviation limit** is rejected instead of silently producing a misleading flat pattern. The persisted 3D draft records the target source signature so a changed mannequin/target invalidates the draft rather than silently moving it.

This is intentionally not a second pattern editor: after extraction, the native Sketcher object is the editable geometry authority. General curved-surface unwrapping, geodesic flattening, darts/relief generation, and bidirectional 2D↔3D editing remain future work.

For reference, FreeCAD's Surface workbench provides Curve on mesh, while the 3D viewer exposes surface picking and mouse callbacks; the Cloth implementation uses the same host interaction model but keeps the resulting PatternPiece Sketcher-authoritative.


The public workbench commands are Sketcher-backed. The historical polygon drafting model remains compatibility-only and is not the normal authoring path.

## Production export

The Pattern workbench also exposes deterministic SVG/DXF-oriented export from authoritative geometry. Export should not mutate the source document.

The export path is downstream from PatternPiece/Sketcher state. It is an adapter, not a second source of geometry.

## Persistence

The saved FCStd document is authoritative. The following should survive save/reload:

- PatternPiece identity;
- source sketch link;
- semantic edge identity;
- pattern metadata;
- validation state.

Generated offset geometry or simulation meshes are not the semantic source.

## Human failure review

A pattern feature is visually suspect when:

- the intended piece outline is no longer visible or closed;
- construction marks are mistaken for the authoritative boundary;
- an edited source sketch changes nothing downstream;
- the user is forced into a separate hidden pattern editor that bypasses Sketcher;
- a stale semantic edge is silently reassigned.

## Automated evidence

Primary fixtures include:

- <code>tests/freecad_pattern_workbench_smoke.py</code>
- <code>tests/freecad_pattern_export_smoke.py</code>
- <code>tests/freecad_screenshot_source.py</code>

Pattern-domain tests also cover persistence, references and topology behavior.

## Source map

Implementation is concentrated under <code>freecad_cloth/pattern/</code>, especially PatternObjects.py, PatternSketch.py, PatternModel.py, PatternExport.py, PatternSync.py and PatternTopologyRepair.py.

Further technical detail: [docs/WORKBENCH_GUIDE.md](../WORKBENCH_GUIDE.md) and [docs/ARCHITECTURE.md](../ARCHITECTURE.md).

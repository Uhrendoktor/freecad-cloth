# 01 · Pattern authoring

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Cloth Pattern workbench showing native Sketcher-backed garment geometry" width="900"></p>

## What the feature is

Cloth Pattern is the 2D garment-authoring stage. Editable geometry remains native FreeCAD Sketcher geometry; Cloth adds garment meaning around it instead of introducing a second polygon editor.

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

**Create piece → edit native Sketch → add garment metadata → recompute → validate → sew**

## 3D Pattern Pen

The **3D Pattern Pen** is the first 3D-to-2D authoring bridge. Select or create the mannequin/drape target, start **Cloth Pattern → 3D Pattern Pen**, and drag over the visible target surface. **Finish Stroke → Pattern** creates a normal native Sketcher-backed PatternPiece.

The first implementation uses a bounded planar projection. A patch that exceeds the configured **Planar deviation limit** is rejected instead of silently producing a misleading flat pattern. The persisted 3D draft records the target source signature so a changed target invalidates the draft rather than silently moving it.

This is intentionally not a second pattern editor: after extraction, native Sketcher remains the editable geometry authority. General curved-surface unwrapping, geodesic flattening, darts/relief generation and bidirectional 2D↔3D editing remain future work.

## Production export

The Pattern workbench exposes deterministic SVG/DXF-oriented export from authoritative geometry. Export should not mutate the source document.

## Persistence

The saved FCStd document is authoritative. PatternPiece identity, source sketch link, semantic edge identity, pattern metadata and validation state should survive save/reload.

Generated offset geometry and simulation meshes are not the semantic source.

## Human failure review

Treat a pattern as visually suspect when the intended piece outline is not visible or closed, construction marks are mistaken for the boundary, source edits have no downstream effect, or a stale semantic edge is silently reassigned.

## Automated evidence

Primary fixtures include:

- `tests/freecad_pattern_workbench_smoke.py`
- `tests/freecad_pattern_export_smoke.py`
- `tests/freecad_screenshot_source.py`

Pattern-domain tests also cover persistence, references and topology behavior.

## Source map

Implementation is concentrated under `freecad_cloth/pattern/`. The package boundary is the durable source map; individual compatibility modules should not be treated as public API.

Further detail: [Workbench guide](../WORKBENCH_GUIDE.md) and [Architecture](../ARCHITECTURE.md).

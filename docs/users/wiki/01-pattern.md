# 01 · Pattern authoring

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Cloth Pattern workbench showing native Sketcher-backed garment geometry" width="900"></p>

## Create a Sketcher-backed pattern piece

Before starting, open a FreeCAD document and create or open the Sketcher sketch that defines the garment piece.

1. In Sketcher, make the outline closed and editable. Add dimensions and constraints where they should govern later edits.
2. Switch to **Cloth Pattern**, select the sketch, and create a PatternPiece from it.
3. Add any required grainline, notches, internal marks, or seam-allowance metadata.
4. Recompute and inspect the result before creating sewing relationships.
5. Save the document so the source sketch and pattern semantics can be checked after reopening.

**Verify the result:** the outline is visible, the source sketch remains the editing authority, and the PatternPiece retains its identity after save/reload. If the piece is invalid, repair the source sketch before trying to sew it.

The 3D Pattern Pen is an optional alternative starting point for bounded near-planar surface patches; it does not replace Sketcher as the editable source. See the [end-to-end user guide](../USER_GUIDE.md) for the complete first-run path.


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

The **3D Pattern Pen** traces a closed boundary on a visible mannequin or Cloth drape target, then extracts a bounded near-planar patch into a normal native Sketcher-backed `PatternPiece`. It is an alternative way to start a pattern—not a replacement for Sketcher.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/surface-pen.png" alt="FreeCAD 3D Pattern Pen task panel with a closed orange surface stroke over the target and Finish Stroke enabled" width="900"></p>

### Trace a boundary and create the pattern

1. Open a document containing the intended mannequin or Cloth target. Select that target when the document contains more than one supported target.
2. Switch to **Cloth Pattern → 3D Pattern Pen**. **Point placement** is the default input mode; the 3D view accepts clicks on the target surface.
3. Choose **Corner point** for a sharp boundary vertex. Choose **Curve point** to add a point that the generated B-spline segment will pass through between its neighboring corner points. Consecutive corner points remain straight lines. Place at least three corner points for a closed pattern boundary.
4. To sketch the boundary yourself using Sketcher, choose **Reference points**. Click at least three points in boundary order. **Create Sketcher Points** creates a native sketch with construction points and opens it for editing; connect the points with native lines, arcs, or B-splines and constrain the resulting outline.
5. To retain the drag-based interaction, switch **Input mode** to **Freehand trace**. Drag on the surface and release to lift the pen; another drag continues the same boundary. Freehand traces currently produce a polyline boundary.
6. For Point placement or Freehand trace, return the endpoint to within **6 mm** of the first point. The orange viewport line previews the closing edge and the status explains the gap. **Finish Stroke → Pattern** becomes enabled once the boundary closes and Point placement has at least three corners.
7. Set **Planar deviation limit** (8 mm by default), then choose **Finish Stroke → Pattern**. This validates the boundary and its distance from a deterministic local plane before creating the persistent draft and pattern piece.
8. Inspect the resulting native Sketcher geometry, then save the FCStd document. The sketch—not the sampled surface anchors—is the editable geometry authority.

The recording below captures the real FreeCAD UI in **Freehand trace** mode through an unfinished stroke, a closed boundary, and the extracted Sketcher result. Point placement is the default interactive mode; the animation documents the retained drag-based alternative. Its stages are captured by the native FreeCAD acceptance fixture, not a hand-drawn illustration.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/surface-pen-workflow.gif" alt="FreeCAD Surface Pen progressing from its task panel through an incomplete stroke and closed outline to the resulting Sketcher pattern" width="900"></p>

After extraction, the target is no longer required to edit the 2D geometry: open the generated native Sketcher sketch to add dimensions or constraints, then use the standard pattern metadata and sewing workflow.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/surface-pen-pattern.png" alt="Native Sketcher outline produced by the Surface Pen; the target is hidden so the editable flat boundary is clear" width="900"></p>

### What is saved

- The **3D Surface Draft** stores sampled world-space anchors, the target link and source signature, closure tolerance, flattening mode, configured planar tolerance, and measured maximum deviation.
- On successful extraction, the draft is marked **Extracted** and hidden. The new `PatternPiece` links back to the draft for provenance and uses a standard `Sketcher::SketchObject` for editable 2D geometry.
- The target signature is checked before extraction. If its source geometry changes after the stroke was recorded, extraction marks the draft **Stale surface target** and refuses to reuse the old samples.
- The viewport stroke is transient while drawing; the finished draft and native pattern/sketch are document state.

### Limits and recovery

The current MVP projects the sampled boundary onto one deterministic local plane. It is **not** general curved-surface unwrapping or geodesic flattening.

| Situation | Expected behavior |
| --- | --- |
| Boundary is still open | Finish stays disabled; return near the first sample or choose **Clear** and redraw. |
| Fewer than three distinct boundary vertices or fewer than three corner points in Point placement mode | Finish stays disabled until the boundary has enough authored corners. |
| Curve points with no three corner points | Finish stays disabled; a surface boundary needs at least three corners. |
| Reference points mode has fewer than three points | Create Sketcher Points stays disabled. |
| Reference points mode | Finish creates construction points and opens a native Sketcher sketch; connect them with ordinary Sketcher geometry. |
| Freehand trace mode | Existing drag-to-sample interaction remains available and produces straight Sketcher segments. |
| Flattened outline self-intersects or has negligible area | Extraction is rejected rather than creating a misleading piece. |
| Maximum deviation exceeds the limit | Extraction is rejected with the measured deviation and configured limit. Increase the limit only if a less-faithful planar approximation is acceptable; otherwise trace a flatter patch. |
| Target source changed after tracing | The draft is marked stale; redraw on the current target. |
| Successful extraction | Continue with the normal Sketcher, pattern-metadata, validation, and sewing commands. |

General curved-surface flattening, dart/relief generation, and bidirectional 2D↔3D editing remain future work. For broader pattern-authoring limits, see the [Workbench guide](../WORKBENCH_GUIDE.md) and [Troubleshooting](../TROUBLESHOOTING.md).

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

Further detail: [Workbench guide](../WORKBENCH_GUIDE.md) and [Architecture](../../developers/ARCHITECTURE.md).

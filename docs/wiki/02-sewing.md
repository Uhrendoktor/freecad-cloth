# 02 · Sewing and semantic correspondence

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png" alt="Cloth Sewing workbench" width="900"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/seam-assignment.gif" alt="Assigning a seam by selecting one edge on each workpiece, reviewing the preview, and committing the seam" width="900"></p>

The animation shows the complete seam workflow in the live FreeCAD window: source and counterpart edges are selected, the semantic seam preview is reviewed, and the seam is committed. In headless CI the harness activates edge subelements through FreeCAD's selection API rather than relying on fragile screen-coordinate hit testing; preview and commit are exercised in the live task panel.

## What the feature is

Cloth Sewing turns authored pattern edges into semantic garment assembly relationships.

The seam is not defined by generated mesh-edge numbering. It refers back to persistent pattern-piece and edge identity, with explicit direction, reversal/correspondence policy and validation state.

## What a human should see

| Visual check | Expected result |
| --- | --- |
| Source edge | The intended authored edge is unambiguous |
| Counterpart edge | The mating edge is explicit |
| Direction | Reversal/correspondence is visible before commit |
| Validation | Length mismatch or invalid references are surfaced instead of hidden |
| 2D ↔ 3D focus | A seam can be inspected in the assembled scene without changing source authority |

## Interaction model

**Select → review → commit**

The sewing UI should never turn an uncertain match into a silent topology guess. Invalid selections are rejected before they become persistent sewing state.

## Correspondence

The sewing model is designed to handle 1:1, 1:N, M:1 and M:N/free relationships.

Curved edges are handled through correspondence data rather than assuming equal vertex counts. Mismatch and reversal should be visible before commit.

## Human failure review

Treat these as visual failures:

- the seam highlights an edge other than the authored one;
- two pieces appear sewn while the displayed semantic relationship disagrees;
- correspondence silently reverses;
- an edited sketch leaves a stale seam looking valid;
- a seam survives only because generated mesh topology happens to retain the same numbering.

## Automated evidence

Relevant fixtures include:

- `tests/freecad_sewing_smoke.py`
- `tests/freecad_sewing_creation_smoke.py`
- `tests/freecad_garment_e2e_smoke.py`

The canonical workflow also exercises the sewn garment through the visual tunic path.

## Source map

Implementation is concentrated under `freecad_cloth/sewing/`. The package boundary is the durable source map; individual compatibility modules should not be treated as public API.

See [Architecture](../ARCHITECTURE.md) for semantic ownership and dependency direction.

## Viewport-first picking and seam identity

You can create a pair without preselecting edges in the tree or relying on tiny subelement clicks:

1. Start **Create Seam**, then choose **Pick edges in viewport**.
2. Click the first outline edge. The panel names side A; then click the matching edge on a different PatternPiece.
3. Review the preview before committing. Both sides carry the same seam color and stable A/B labels (for example, S3-A and S3-B); directional arrows and notches expose traversal/reversal. Cancel removes the staged relationship.

For a network/free-sewing relationship, pick all desired edges, stop viewport picking, then press Preview. Native selection remains available as a precision/fallback workflow. The preview and persisted object use the same semantic edge-reference model; viewport interaction does not create a second geometry authority.

The colored paths and A/B tags are transient viewport overlays, not document objects. They are regenerated from valid semantic seam references after recompute, document restore, view entry, and workbench activation. The object's SeamId remains canonical; colors and short labels are only presentation. Invalid or stale edge references are deliberately not drawn as valid seams.

Open **Seam Overlay Options** under Sewing → Validation & View to hide or show the colored overlays and choose whether linework and labels respect foreground geometry. A/B labels appear only while the pointer is over a sewn pattern edge; moving away hides them. When reviewing a crowded scene, verify the seam ID and side suffix as well as color. Color alone is not a sufficient identity cue, and directional marks should agree before Commit.

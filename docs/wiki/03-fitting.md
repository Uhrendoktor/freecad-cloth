# 03 · Direct fitting and arrangement

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.png" alt="Interactive Arrange task panel and viewport" width="900"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png" alt="Sewn garment arranged around the mannequin before simulation" width="900"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/arrangement-anchor.gif" alt="Interactive Arrange enters surface-pick mode, a selected target face becomes a named blue snap anchor, and the marker appears in the viewport" width="900"></p>

The first animation shows how to create a surface-aware snap anchor. Name it, choose a wrap direction, select **Pick surface in viewport**, then click a face on the configured avatar or target geometry. The persistent marker records the target object, selected subelement, target-local location, and geometry reference. For mesh targets, it also stores a triangle index and barycentric coordinates so the marker follows the same surface region as avatar vertices move during posing.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.gif" alt="A flat garment pattern piece moving toward a blue crosshair arrangement anchor; the preview snaps to it and release commits the placement" width="900"></p>

A blue crosshair marks the pattern piece's placement-origin target. A picked surface anchor follows object translation/rotation through the target placement. On deforming mesh targets (including the built-in avatar), the stored triangle/barycentric reference follows vertex movement as long as triangle connectivity remains stable. Anchors turn red and are excluded from snapping if the target is replaced, its surface topology changes, or the underlying non-mesh shape geometry changes. The point controls piece placement—it is not a cloth pin or a surface constraint. Releasing the drag commits the snapped placement.

The recordings show the live task panel and viewport. Headless acceptance exercises the task panel's selection and drag callbacks because native viewport injection is unstable in some FreeCAD/Pivy builds.

## Arrange pieces before simulation

Start with valid PatternPieces and a selected, current **DrapeTarget**. The GIF shows the viewport snap interaction; the expected result is the saved placement, not the temporary drag preview.

1. Open **Cloth Simulation** and enter **Interactive Arrange**.
2. To create a target-aware snap point, enter a name, choose a wrap direction, select **Pick surface in viewport**, and click a face on the configured avatar/target.
3. Drag a pattern piece in the viewport. With snapping enabled, approach the blue marker until the snap preview appears.
4. Release to commit the placement as a FreeCAD transaction. Repeat for the remaining pieces.
5. Anchors follow target placement changes and mesh pose edits when the referenced surface topology remains compatible. If an anchor turns red after a topology change, shape edit, or target replacement, recreate it before using it. Review the garment-to-target relationship before simulation; reset and arrange again if a piece is accidentally placed or overlaps unexpectedly.

**Verify the result:** placements remain after save/reopen, the target is the intended collision authority, and the garment is intentionally positioned before Run. Fitting does not repair invalid sewing relationships or define collision geometry.


## What the feature is

Interactive Arrange is the direct-manipulation fitting stage. The viewport is the primary surface for moving garment pieces.

The fitting scene persists placements and arrangement metadata. A mouse drag is not the document authority; releasing the drag commits a normal FreeCAD transaction.

## What a human should see

| Visual check | Expected result |
| --- | --- |
| Active piece | The piece being moved is visually obvious |
| Drag | The garment follows the pointer in the 3D scene |
| Snap approach | A snap target/marker becomes visible near an arrangement point |
| Release | The new placement is visibly committed |
| Reset | The garment can return to its saved home arrangement |
| Framing | Fit view keeps the target and garment readable |

## Snap-driven interaction

The normal flow is:

<strong>Select piece → drag → approach arrangement point → snap marker appears → release → placement commits</strong>

Snap is optional. With snap disabled, free dragging remains available.

Each drag is intended to be one undoable FreeCAD transaction rather than a stream of tiny document edits.

## Relationship to DrapeTarget

Fitting does not own collision geometry. It identifies and prepares the fitting scene, while <code>DrapeTarget</code> remains the target authority used by simulation.

A target may be:

- the native human mannequin;
- an ordinary FreeCAD Shape;
- PartDesign/Body geometry;
- Mesh geometry.

The fitting scene remains target-neutral.

## What persists

A saved document can carry:

- piece placements;
- coordinate-based arrangement points and target-aware surface-anchor references;
- fitting-scene state;
- selected target identity;
- measurements where supported.

Transient mouse position, hover highlights and snap previews are not persistence state.

## Human failure review

A fitting implementation should be considered suspect when:

- the viewport interaction only changes a transient preview;
- snapping is visual but not persisted;
- Reset produces a different home arrangement each time;
- a target change silently leaves stale collision state;
- moving one piece mutates unrelated pieces without explicit semantics.

## Automated evidence

Primary GUI acceptance:

<code>tests/freecad_interactive_arrange_acceptance.py</code>

Source:

- <code>freecad_cloth/avatar/FittingGui.py</code>
- <code>freecad_cloth/avatar/FittingCommands.py</code>
- <code>freecad_cloth/avatar/AvatarFitting.py</code>
- <code>freecad_cloth/avatar/AvatarArrangement.py</code>

The generated <code>interactive-arrange.png</code> is the public visual proof of the current viewport workflow.

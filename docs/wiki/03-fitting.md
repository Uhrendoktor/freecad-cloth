# 03 · Direct fitting and arrangement

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.png" alt="Interactive Arrange task panel and viewport" width="900"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png" alt="Sewn garment arranged around the mannequin before simulation" width="900"></p>

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
- arrangement points;
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

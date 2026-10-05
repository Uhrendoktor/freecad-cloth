# 02 · Sewing and semantic correspondence

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png" alt="Cloth Sewing workbench" width="900"></p>

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

Semantic seam selection is a user action; committed seam state belongs to the FreeCAD document.

## Interaction model

<strong>Select → review → commit</strong>

The sewing UI should never turn an uncertain match into a silent topology guess.

For staged operations, the task panel provides a recoverable interaction model. Invalid selections are rejected before they become persistent sewing state.

## Correspondence

The sewing model is designed to handle:

- 1:1 relationships;
- 1:N relationships;
- M:1 relationships;
- M:N/free relationships.

Curved edges are handled through correspondence data rather than assuming equal vertex counts. Mismatch and reversal should be visible before the user commits the relationship.

## Human failure review

Treat these as visual failures:

- the seam highlights an edge other than the authored one;
- two pieces appear sewn while the displayed semantic relationship disagrees;
- correspondence silently reverses;
- an edited sketch leaves a stale seam looking valid;
- a seam survives only because generated mesh topology happens to retain the same numbering.

## Automated evidence

Relevant fixtures include:

- <code>tests/freecad_sewing_smoke.py</code>
- <code>tests/freecad_sewing_creation_smoke.py</code>
- <code>tests/freecad_garment_e2e_smoke.py</code>

The canonical workflow also exercises the sewn garment through the visual tunic path.

## Source map

Implementation is concentrated under <code>freecad_cloth/sewing/</code>, especially SeamGraph.py, SeamReference.py, SewingObjects.py, SewingSemantics.py, SewingCorrespondence.py, SewingCreationGui.py and SewingGui.py.

See [docs/ARCHITECTURE.md](../ARCHITECTURE.md) for semantic ownership and dependency direction.

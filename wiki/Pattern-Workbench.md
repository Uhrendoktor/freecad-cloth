# Cloth Pattern Workbench

## What it is for

**Cloth Pattern** is the editable 2D garment-authoring layer.

It is designed around FreeCAD-native Sketcher geometry rather than a second hidden geometry editor.

## Core concepts

| Concept | What you do with it |
| --- | --- |
| PatternPiece | Turn editable sketch geometry into a persistent garment piece |
| Semantic edge | Keep stable identity for sewing relationships |
| Seam allowance | Define derived offset geometry for inspection and export |
| Grainline / marks | Record garment-construction metadata |
| Validation | Surface invalid topology instead of silently repairing it |

## Recommended workflow

1. Build or open the source geometry in Sketcher.
2. Create the PatternPiece.
3. Define meaningful edges and garment metadata.
4. Add seam allowances and marks.
5. Recompute and validate before sewing.

> **Rule of thumb:** edit geometry in Sketcher; use Cloth to attach garment meaning to that geometry.

## What happens after geometry changes?

A downstream semantic relationship can become stale when its source topology changes.

That is intentional. Cloth prefers an explicit repair/remap step over silently assigning a seam to a different edge.

## Visual starting point

The repository's visual acceptance path includes a tunic example and stable generated screenshots. The core pattern workflow itself remains usable with a small Sketcher model.

# Cloth Sewing Workbench

## What it is for

**Cloth Sewing** turns pattern pieces into a semantic construction graph.

## A seam is more than two mesh edges

A seam records garment relationships such as:

- participating pieces and semantic edge ranges;
- orientation and reversal;
- correspondence policy;
- stitch or construction kind;
- validation state.

The representation is designed to support 1:1, 1:N, M:1 and M:N relationships without depending on particle or triangle counts.

## Recommended workflow

1. Select the source edge ranges.
2. Preview the proposed relationship.
3. Check direction and correspondence.
4. Commit the seam.
5. Recompute and save.
6. Re-check after later pattern edits.

## Curves and correspondence

Curved seam ranges are compared by physical arc length so that parameterization differences do not silently distort the intended pairing.

Before committing a mismatch, inspect the direction, reversal and reported correspondence information.

## Visual inspection

Use the 2D sewing view to verify the seam relationship.

When needed, use the seam-focus command to fit a selected seam in 3D and inspect its placed or world-space presentation.

## Repair philosophy

If an upstream sketch changes enough to invalidate a seam, repair or remap it explicitly.

Cloth intentionally fails closed instead of silently retargeting a relationship to a different edge.

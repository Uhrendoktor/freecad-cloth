# Simulation visual review

Simulation changes are accepted through human-reviewable rendered evidence. Human review starts with the images and animations; logs and numerical manifests are secondary evidence.

## Required evidence

Every simulation implementation PR or experiment issue should expose actual rendered PNGs containing launch/step 0, representative checkpoints (normally steps 15, 45 and 90), and final front, rear, right, left, top and bottom views. Production garment validation also exposes a mannequin drape animation.

The normal simulation gate additionally publishes a progressive collision ladder for cube and mannequin targets.

## Collision ladder

The ladder is ordered from simple to complex:

| Rungs | Scenario |
| --- | --- |
| 1–2 | Single cloth panel on a cube, pinned then unpinned |
| 3–5 | Two cube panels, no seam then small and large seam offsets |
| 6–7 | Single cloth panel on the production mannequin, pinned then unpinned |
| 8–10 | Two mannequin panels, no seam then small and large seam offsets |

Each rung records steps 0, 1, 5, 15, 45 and 90. The gate stops at the first failed rung. A failure is useful evidence; passing later rungs never masks an earlier failure.

The collision review explicitly checks that the cloth remains outside the target within the configured small SDF/mesh discretization allowance. Visible penetration is a failure even when the solver remains finite.

## Human review order

Review the evidence in this order:

1. Pattern source — native Sketcher geometry and PatternPiece authority.
2. Sewing — seam identity, direction, markers and correspondence.
3. Cube collision — falling cloth, impact/contact, no visible clipping.
4. Mannequin collision — shoulder/side contact, body clearance, seam behavior, fold development.
5. Final garment — arranged versus draped 360° views.
6. Diagnostics — six-side coverage and stress visualization.

## What constitutes a visual failure

A simulation should be treated as visually invalid when the rendered media shows cloth entering a collision target, exploding or collapsing geometry, broken or detached seams, sudden topology changes, implausible rigid-sheet behavior, or a final silhouette that no longer reads as cloth.

## Experimental discipline

One bounded hypothesis, one active implementation PR, one falsifier. Rejected or superseded experiments remain historical evidence and must not become competing implementation authorities.

## CI contract

The canonical workflow runs the collision ladder as a normal simulation gate and uploads its rendered evidence. The PR simulation evidence job also publishes human-reviewable PNGs from the exact PR head. A simulation run that produces no required image evidence fails closed.

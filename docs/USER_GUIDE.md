# User guide

## Start with the basic example

After installation, open the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

For a first validation, follow the **Blanket over Cube** example in [Examples](EXAMPLES.md). Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube.

## Typical garment workflow

1. Create or open a native Sketcher pattern in **Cloth Pattern** and turn it into a PatternPiece. Keep Sketcher as the geometry authority.
2. Use **Cloth Sewing** to select matching semantic edges and create seams. Editing an upstream Sketcher edge can invalidate a downstream seam rather than silently retargeting it.
3. In **Cloth Sewing**, create a Fitting Scene, add the intended PatternPieces, and establish saved home placements/Arrangement Points.
4. In **Cloth Simulation**, select or rebuild the persistent DrapeTarget. A target can be a mannequin collision surface or supported generic FreeCAD geometry.
5. Open **Arrange / Fit** when needed. With authored GarmentAnchors available, **Snap pieces to target** applies bounded rigid placement against the current DrapeTarget; **Reset arrangement** restores saved home placements.
6. Set simulation quality and fabric presentation. Physical material parameters affect the solver; color, roughness, specular response and transparency affect viewport rendering.
7. Choose pins and run the simulation. Stale or non-finite states are fail-closed.
8. Inspect the result and diagnostics before export or saving a final document.

## Seams and visual inspection

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use the seam-focus command to fit a selected seam in 3D, and the Sketcher-side seam command to edit the authoritative source edge.

## Fabric presentation

Presentation properties are persisted on the native Fabric Material object and are separate from the physical solver parameters.

## Persistence and recovery

After pattern, seam-source or drape-target changes, rebuild or repair dependent derived state before simulation/export. Cloth intentionally reports stale dependencies instead of silently using outdated derived geometry.

For debugging, compare local results with the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow and attach the relevant CI artifact/log rather than editing generated evidence manually.

## Arrange / Fit

The fitting stage is persistent document state, not transient solver state. **Snap pieces to target** requires a current DrapeTarget and authored GarmentAnchors, applies bounded rigid placement, and verifies the complete PatternPiece surface against target clearance. It does not infer arbitrary garment-body correspondences.

After changing the avatar or target, use **Refresh target** before fitting again.

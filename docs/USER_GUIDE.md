# User guide

## Start with the basic example

After installation, open the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

For a first validation, follow the **Blanket over Cube** example in [Examples](EXAMPLES.md). Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube.

## Typical garment workflow

1. Create or open a native Sketcher pattern in **Cloth Pattern** and turn it into a PatternPiece. Keep Sketcher as the geometry authority.
2. Use **Cloth Sewing** to select matching semantic edges and create seams. Editing an upstream Sketcher edge can invalidate a downstream seam rather than silently retargeting it.
3. In **Cloth Simulation**, select or rebuild a DrapeTarget. A target can be a mannequin collision surface or supported generic FreeCAD geometry.
4. Set simulation quality and fabric presentation. Physical material parameters affect the solver; color, roughness, specular response and transparency affect viewport rendering.
5. Arrange garment pieces relative to the avatar before simulation. Arrangement points are fitting metadata; they are not solver pins.
6. Choose the simulation pin policy. **Use automatic default pins** preserves the legacy corner-pin behavior when no explicit pins are supplied. Turn it off for a deliberately unpinned arranged garment, or enter explicit particle indices when constraints are part of the intended fixture. The task panel now shows this state instead of silently treating an empty pin field as a pin policy.
7. Run the simulation. Stale or non-finite states are fail-closed.
8. Inspect the result and diagnostics before export or saving a final document.

## Seams and visual inspection

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use the seam-focus command to fit a selected seam in 3D, and the Sketcher-side seam command to edit the authoritative source edge.

## Fabric presentation

Presentation properties are persisted on the native Fabric Material object and are separate from the physical solver parameters.

## Persistence and recovery

After pattern, seam-source or drape-target changes, rebuild or repair dependent derived state before simulation/export. Cloth intentionally reports stale dependencies instead of silently using outdated derived geometry. If the target is stale or missing, repair the DrapeTarget rather than compensating with a different pin layout.

For debugging, compare local results with the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow and attach the relevant CI artifact/log rather than editing generated evidence manually.
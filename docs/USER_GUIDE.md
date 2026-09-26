# User guide

## First run: two different paths

After installation, open the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

For the installation smoke test, follow the **Blanket over Cube** example in [Examples](EXAMPLES.md). Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube. This path is intentionally about basic cloth/collision behavior and manual pinning; it does not test mannequin fitting.

For the garment path, continue with the **Tunic** example. It uses the fitting/arrangement layer before simulation and therefore tests a different part of the product.

## Typical garment workflow

1. Create or open a native Sketcher pattern in **Cloth Pattern** and turn it into a PatternPiece. Keep Sketcher as the geometry authority.
2. Use **Cloth Sewing** to select matching semantic edges and create seams. Editing an upstream Sketcher edge can invalidate a downstream seam rather than silently retargeting it.
3. In **Cloth Sewing**, create an **Avatar Fitting Scene**, add the selected PatternPieces, and arrange them explicitly. The current fitting commands expose persistent arrangement points and **Reset Arrangement**; use those controls to establish the garment start pose before simulation.
4. In **Cloth Simulation**, create or refresh the mannequin **Drape Target** and verify that the target is valid. A target can also be supported generic FreeCAD geometry.
5. Set simulation quality and fabric presentation. Physical material parameters affect the solver; color, roughness, specular response and transparency affect viewport rendering.
6. Treat pinning as a separate simulation input on current main. The documented fitting path does not promise automatic target-relative, pin-free tunic placement.
7. Inspect the result and diagnostics before export or saving a final document. Stale or non-finite states are fail-closed.

## Seams and visual inspection

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use the seam-focus command to fit a selected seam in 3D, and the Sketcher-side seam command to edit the authoritative source edge.

## Fabric presentation

Presentation properties are persisted on the native Fabric Material object and are separate from the physical solver parameters.

## Persistence and recovery

After pattern, seam-source or drape-target changes, rebuild or repair dependent derived state before simulation/export. Cloth intentionally reports stale dependencies instead of silently using outdated derived geometry.

For debugging, compare local results with the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow and attach the relevant CI artifact/log rather than editing generated evidence manually.
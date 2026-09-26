# User guide

## Start with the basic example

After installation, open the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

For a first validation, follow the **Blanket over Cube** example in [Examples](EXAMPLES.md). Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube.

## Typical garment workflow

1. Create or open a native Sketcher pattern in **Cloth Pattern** and turn it into a PatternPiece. Keep Sketcher as the geometry authority.
2. Use **Cloth Sewing** to select matching semantic edges and create seams. Editing an upstream Sketcher edge can invalidate a downstream seam rather than silently retargeting it.
3. In the fitting/arrangement path, select exactly one current DrapeTarget and add the garment PatternPieces to the fitting scene. Use **Snap pieces to target** to place them from the authoritative collision surface with bounded outward clearance; the operation is solver-neutral and can be reversed with **Reset Arrangement**.
4. In **Cloth Simulation**, refresh or rebuild the same DrapeTarget and confirm it is ready before simulation. A target can be a mannequin collision surface or supported generic FreeCAD geometry.
5. Set simulation quality and fabric presentation. Physical material parameters affect the solver; color, roughness, specular response and transparency affect viewport rendering.
6. Choose the explicit pin mode and run the simulation. **None** is the deliberate no-global-pin mode used for arranged garments; **Automatic** and **Explicit** retain the existing blanket/constraint workflows. Stale or non-finite states are fail-closed.
6. Inspect the result and diagnostics before export or saving a final document.

## Seams and visual inspection

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use the seam-focus command to fit a selected seam in 3D, and the Sketcher-side seam command to edit the authoritative source edge.

## Fabric presentation

Presentation properties are persisted on the native Fabric Material object and are separate from the physical solver parameters.

## Persistence and recovery

After pattern, seam-source or drape-target changes, rebuild or repair dependent derived state before simulation/export. Cloth intentionally reports stale dependencies instead of silently using outdated derived geometry.

For debugging, compare local results with the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow and attach the relevant CI artifact/log rather than editing generated evidence manually.
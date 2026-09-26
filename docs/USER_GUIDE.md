# User guide

## Start with the basic example

After installation, open the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

For a first validation, follow the **Blanket over Cube** example in [Examples](EXAMPLES.md). Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube.

## Typical garment workflow

1. Create or open a native Sketcher pattern in **Cloth Pattern** and turn it into a PatternPiece. Keep Sketcher as the geometry authority.
2. Use **Cloth Sewing** to select matching semantic edges and create seams. Editing an upstream Sketcher edge can invalidate a downstream seam rather than silently retargeting it.
3. In **Cloth Sewing**, create/select the fitting scene and add the garment pieces. Select exactly one persistent **DrapeTarget** and the pieces, then use **Snap pieces to target** to place them with bounded rigid translation and conservative outward collision-surface clearance. The operation preserves rotation/relative spacing, records the resulting PiecePlacements, and **Reset Arrangement** restores HomePlacements.
4. In **Cloth Simulation**, verify the same DrapeTarget is attached to the simulation. The target is authoritative; missing, stale, unbuilt or invalid targets block simulation rather than falling back to the avatar proxy.
5. Set simulation quality, fabric presentation, and pinning mode. **Automatic** preserves legacy boundary-pin behavior, **Explicit** uses only `PinSelection`, and **None** creates a genuinely pinless solver scene.
6. Run the simulation. Inspect the target status, finite-state indicator, seam presentation and diagnostics before export or saving a final document.

## Seams and visual inspection

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use the seam-focus command to fit a selected seam in 3D, and the Sketcher-side seam command to edit the authoritative source edge.

## Fabric presentation

Presentation properties are persisted on the native Fabric Material object and are separate from the physical solver parameters.

## Persistence and recovery

After pattern, seam-source or drape-target changes, rebuild or repair dependent derived state before simulation/export. Cloth intentionally reports stale dependencies instead of silently using outdated derived geometry.

For debugging, compare local results with the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow and attach the relevant CI artifact/log rather than editing generated evidence manually.
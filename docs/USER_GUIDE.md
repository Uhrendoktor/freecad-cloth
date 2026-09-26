# User guide

## Start with the basic example

After installation, open the **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** workbenches from the FreeCAD workbench selector.

For a first validation, follow the **Blanket over Cube** example in [Examples](EXAMPLES.md). Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube.

## Typical garment workflow

1. Create or open a native Sketcher pattern in **Cloth Pattern** and turn it into a PatternPiece. Keep Sketcher as the geometry authority.
2. Use **Cloth Sewing** to select matching semantic edges and create seams. Editing an upstream Sketcher edge can invalidate a downstream seam rather than silently retargeting it.
3. In **Cloth Simulation**, select or rebuild a `DrapeTarget`. A target can be a mannequin collision surface or supported generic FreeCAD geometry. The **Context** group shows the persistent target and its current status.
4. Use **Arrange / Fit…** from the Simulation task panel to hand the current garment pieces to the persistent fitting stage. **Refresh target** is the visible target-recovery control: it re-enables a disabled target, opens target editing for an invalid/unassigned target, or refreshes the current target after a source change. **Reset arrangement** restores the saved pre-arrangement placements.
5. The target-aware placement integration exposes `ClothFitting_SnapPiecesToTarget`. When present, it performs a bounded rigid translation against the persistent `DrapeTarget`, validates clearance for the full selected pieces, and rolls the placement back on failure; it is not conformal deformation. Use **Snap pieces to target** only for that bounded placement operation, not as a solver or pinning substitute.
6. Set simulation quality and fabric presentation. Physical material parameters affect the solver; color, roughness, specular response and transparency affect viewport rendering.
7. Choose pins using the exact `PinMode` semantics: **Automatic** preserves legacy behavior, using `PinSelection` when present and otherwise the existing automatic boundary pins; **Explicit** uses only `PinSelection`; **None** creates the simulation with zero solver pins. The canonical tunic fixture uses **None** with an empty pin selection.
8. Run the simulation. Stale or non-finite states are fail-closed, so repair or refresh the target before advancing the solver.
9. Inspect the result and diagnostics before export or saving a final document.

## Seams and visual inspection

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use the seam-focus command to fit a selected seam in 3D, and the Sketcher-side seam command to edit the authoritative source edge.

## Fabric presentation

Presentation properties are persisted on the native Fabric Material object and are separate from the physical solver parameters.

## Persistence and recovery

After pattern, seam-source or drape-target changes, rebuild or repair dependent derived state before simulation/export. Cloth intentionally reports stale dependencies instead of silently using outdated derived geometry.

For debugging, compare local results with the FreeCAD/Triangle/Tissu versions recorded by the canonical workflow and attach the relevant CI artifact/log rather than editing generated evidence manually.
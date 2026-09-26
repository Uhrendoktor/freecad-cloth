# User guide

This guide is the normal human workflow. For installation details, use [INSTALLATION.md](INSTALLATION.md); for exact command/task-panel reference, use [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md).

## First run: Blanket over Cube

Use the blanket before the tunic. It isolates pattern, collision and simulation problems without adding sewing or mannequin-fitting complexity.

The validated scenario is a **200 × 200 mm** native Sketcher rectangle over a **180 × 180 × 60 mm** FreeCAD cube. The cube is represented by a persistent `DrapeTarget`, and the fixture verifies real cloth movement and rendered viewport captures.

The current simulation quality panel exposes **Pinning mode** with **Automatic**, **Explicit**, and **None**:

- **Automatic** preserves legacy behavior and uses `PinSelection` when it is present, otherwise the existing automatic boundary pins.
- **Explicit** uses only `PinSelection`.
- **None** creates the simulation with zero solver pins.

The quality panel does not provide a mesh-vertex picker for creating `PinSelection`. The canonical blanket fixture therefore remains the authoritative executable proof for the two-corner pinning setup.

See the complete blanket recipe and artifact behavior in [EXAMPLES.md](EXAMPLES.md).

## Normal garment workflow

The supported human workflow is:

```
Pattern → Sewing → Arrange/Fit → DrapeTarget → Simulate → Diagnose → Output
```

### 1. Pattern

Open **Cloth Pattern**.

For a new piece, use **Create Pattern Piece Task** (`ClothPattern_CreatePieceTask`) or **Create Pattern Piece With Sketch** (`ClothPattern_CreatePiece` / `ClothPattern_CreatePieceWithSketch`). The normal geometry authority is native FreeCAD Sketcher.

For an existing native Sketcher object:

1. Select the Sketcher object.
2. Run **Create Pattern Piece From Selected Sketch** (`ClothPattern_CreateFromSketch`).
3. Recompute.
4. Select the resulting PatternPiece and use **Edit Sketch** (`ClothPattern_EditSketch`) when geometry must change.

For a production garment root, use **Create Garment** (`ClothPattern_CreateGarment`).

The legacy PatternDrafting polygon editor remains compatibility-only for older documents; it is not the normal new-authoring path.

### 2. Sewing

Open **Cloth Sewing** and select compatible semantic edges from the PatternPieces.

For a normal pair seam:

1. Select exactly two pattern edges on two different pieces.
2. Run **Create Seam** (`ClothSewing_CreateSeam`).
3. In the staged task panel choose **Preview**.
4. Review validation.
5. Choose **Commit** to persist the seam, or **Cancel** to discard the staged transaction.

For 1:N, M:1 or M:N relationships, use **Create M:N Sewing** (`ClothSewing_CreateMNSewing`). Use **Create Sewing Operation** (`ClothSewing_CreateOperation`) for persistent correspondence/operation settings.

Use **Validate Sewing** (`ClothSewing_Validate`) after editing. If the existing semantic edge still exists, **Repair Seam** (`ClothSewing_RepairSeam`) can repair reversible/invalid-range correspondence. If the semantic edge itself disappeared, recreate the seam; do not retarget it by generated mesh edge order.

#### Seam presentation

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. Use **Show Sewing 2D** (`ClothSewing_Show2D`) or **Focus Seam in 3D** (`ClothSewing_FocusSeam3D`) when the seam is difficult to identify.

**Edit Seam Side A in Sketcher** and **Edit Seam Side B in Sketcher** open the authoritative native Sketcher source used by the seam.

### 3. Arrange / Fit

For mannequin fitting, use the **Cloth Sewing** fitting/avatar commands.

1. Run **Create Avatar** (`ClothFitting_CreateAvatar`) when a mannequin is not already present.
2. Use **Create Fitting Scene** (`ClothFitting_CreateScene`) and add the selected PatternPieces with **Add Selected Pattern Pieces** (`ClothFitting_AddPieces`).
3. Create or edit persistent placement metadata with **Create Arrangement Point**, **Set Arrangement Point**, and **Apply Selected Arrangement**.
4. Use **Reset Arrangement** (`ClothFitting_ResetArrangement`) for recovery.

Arrangement is explicit and persistent. The current human-facing journey does not claim a general automatic “snap garment to body” operation; only separately accepted behavior should be added to this guide.

For generic CAD targets, ordinary FreeCAD Shape/PartDesign/Body/Mesh geometry can also supply the target-neutral `DrapeTarget`.

### 4. DrapeTarget

Open **Cloth Simulation** and create or edit the persistent target.

For generic geometry, select the FreeCAD Shape/Mesh and run **Create Target** (`ClothDrape_CreateTarget`). For the bundled human mannequin, use **Create Mannequin Target** (`ClothDrape_CreateMannequinTarget`).

Use **Edit Drape Target** (`ClothDrape_EditTarget`) to inspect the persistent target. The target types are exactly **Mannequin** and **FreeCAD Geometry**.

After changing source geometry, placement, tessellation or collision thickness, use **Refresh Drape Target** (`ClothDrape_RefreshTarget`) before simulation.

A target can report **missing**, **disabled**, **invalid**, **unassigned**, **unbuilt**, **stale**, or **ready**. **Step** and **Run 30** are intentionally fail-closed unless the target is valid/current.

### 5. Simulate

Create/select the simulation with **Create Simulation** (`ClothSimulation_Create`) and open **Simulation Controls** (`ClothSimulation_Edit`).

The quality panel separates:

- **Preset**: Fast / Balanced / Final
- **Pinning mode**: Automatic / Explicit / None
- **Particle distance**, **Solver iterations**, **Solver substeps**
- Fabric density, thickness, stretch, shear, bend, friction
- Fabric color, specular, roughness and transparency
- Avatar skin offset and collision radius
- **Step** (`ClothSimulation_Step`)
- **Run 30** (`ClothSimulation_Run`)
- **Reset** (`ClothSimulation_Reset`)

The simulation scene persists the intended PatternPieces in `ClothPieces`; inspect those links before diagnosing a missing garment.

### 6. Diagnose and iterate

After a valid drape, use **Cloth Diagnostics** (`ClothDrape_Diagnostics`) for the supported stress/strain/fit/pressure analysis path.

When something changes upstream:

```
Pattern edit
  → recompute
  → validate/repair sewing if needed
  → refresh DrapeTarget if needed
  → simulate again
```

Cloth intentionally fails closed on stale derived state rather than silently consuming an outdated target or semantic seam reference.

## Current tunic behavior

The exact current-main release record marks the P0 end-to-end workflow complete and the tunic visual/simulation audit passed. The validated path covers native Sketcher pattern pieces, semantic sewing, a production mannequin/`DrapeTarget`, persisted quality/material settings, diagnostics, persistence/determinism and production 2D export.

The acceptance fixture uses **PinMode=None** with zero solver pins and target-relative starting placement. This is a fixture-specific acceptance condition; it is not evidence that the general Fitting Scene UI performs automatic commercial-style body snapping.

Use [EXAMPLES.md](EXAMPLES.md) for the shortest tunic walkthrough and [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) for command-level reference.

## Recovery checklist

**No workbench:** fix the FreeCAD `Mod` installation and restart.

**No pattern geometry:** edit the native Sketcher source and recompute.

**Seam invalid:** run **Validate Sewing**; repair only when the existing semantic edge survives, otherwise recreate the seam.

**Target stale:** open **Edit Drape Target** → verify source/provider → **Refresh Drape Target**.

**Simulation blocked:** read the target status first. A blocked Run is usually a target-state problem, not a solver-quality setting.

**Cloth missing:** inspect the simulation object's `ClothPieces` links and recompute.

**Tunic collision problem:** verify persistent arrangement/placement and DrapeTarget refresh before changing unrelated solver quality.
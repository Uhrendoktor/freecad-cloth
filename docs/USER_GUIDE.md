# User guide

This guide is the normal human workflow. For installation details, use [INSTALLATION.md](INSTALLATION.md); for exact command/task-panel reference, use [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md).

## First run: Blanket over Cube

Use the blanket before the tunic. It isolates pattern, collision and simulation problems without adding sewing or mannequin-fitting complexity.

The validated scenario is a 200 × 200 mm native Sketcher rectangle over a 180 × 180 × 60 mm FreeCAD cube. It creates a persistent DrapeTarget from that cube and proves that the cloth moves toward and around the target.

The current public simulation controls are quality/material controls plus **Step**, **Run 30**, and **Reset**. Pinning is persisted as simulation input, but the quality task panel does not provide a direct mesh-vertex picking tool; the canonical visual fixture supplies the pin indices programmatically. For a human smoke test, treat the canonical visual fixture as the authoritative proof and do not assume a point-and-click pin workflow that is not present in the current UI.

See the complete recipe in [EXAMPLES.md](EXAMPLES.md).

## Normal garment workflow

The supported human workflow is:

    Pattern → Sewing → Arrange/Fit → Drape Target → Simulate → Diagnose → Output

### 1. Pattern

Open **Cloth Pattern**.

For a new piece, use **Create Pattern Piece Task** (ClothPattern_CreatePieceTask) or **Create Pattern Piece With Sketch** (ClothPattern_CreatePiece). The normal geometry authority is native FreeCAD Sketcher.

For an existing native Sketcher object:

1. Select the Sketcher object.
2. Run **Create Pattern Piece From Selected Sketch** (ClothPattern_CreateFromSketch).
3. Recompute.
4. Select the resulting PatternPiece and use **Edit native Sketch…** for geometry edits.

Keep Sketcher as the geometry authority. The legacy polygon drafting editor is compatibility-only for older documents.

### 2. Sewing

Open **Cloth Sewing** and select semantic edges from two different PatternPieces.

For a normal pair seam:

1. Select exactly two pattern edges on two different pieces.
2. Run **Create Seam** (ClothSewing_CreateSeam).
3. In the staged task panel, choose **Preview**.
4. Review the validation result.
5. Choose **Commit** to persist the seam, or **Cancel** to discard the staged change.

For 1:N, M:1 or M:N relationships, use **Create M:N Sewing** and the same Preview → Commit pattern. **Create Sewing Operation** then exposes seam correspondence, orientation, tolerance and stitch-sample controls.

Use **Validate Sewing** after editing. If a seam is invalid because its existing semantic edge is stale or its correspondence settings are repairable, use **Repair Seam**. If the semantic edge itself disappeared, recreate the seam instead of changing an ordinal edge reference by hand.

The sewing view has deterministic seam colors. **Focus Seam in 3D** isolates and fits the selected seam, and **Edit Seam Side A/B in Sketcher** opens the authoritative Sketcher edge for direct correction.

### 3. Arrange / Fit

For mannequin fitting, use the **Fitting & Avatar** commands in the **Cloth Sewing** workbench.

A practical sequence is:

1. Run **Create Avatar** (ClothFitting_CreateAvatar) when a mannequin is not already present.
2. Use **Edit Avatar** to set measurements, provider, pose and skin offset. The current provider default is the bundled MakeHuman HM08-based mannequin.
3. Create a **Fitting Scene** (ClothFitting_CreateScene) and add the selected PatternPieces with **Add Selected Pattern Pieces** (ClothFitting_AddPieces).
4. Use **Create Arrangement Point**, **Set Arrangement Point**, and **Apply Selected Arrangement** to establish persistent placements.
5. Use **Reset Arrangement** when you need to return pieces to their saved pre-arrangement placement.

Arrangement is explicit and persistent. The current release does **not** provide a general automatic “snap garment to body” operation comparable to a commercial avatar-fitting system. The arrangement-point contract is the current documented placement mechanism.

For generic CAD targets, the same fitting model can work with ordinary FreeCAD Shape/PartDesign/Body/Mesh geometry through the target-neutral DrapeTarget contract.

### 4. Drape Target

Open **Cloth Simulation** and create or edit the persistent target.

For a mannequin, use **Create Mannequin Target** (ClothDrape_CreateMannequinTarget). For generic geometry, select the FreeCAD Shape/Mesh and use **Create Target** (ClothDrape_CreateTarget).

In **Edit Drape Target**:

- Provider: **Mannequin** or **FreeCAD Geometry**
- Source: the actual collision object
- Preset: **Preview**, **Normal**, or **Final**
- Collision thickness: the desired clearance
- **Apply & Refresh** to rebuild collision data

After changing the target source or collision settings, refresh it before simulation.

### 5. Simulate

Create or select the **Cloth Simulation** object and open **Simulation Controls** (ClothSimulation_Edit).

Use:

- **Preset**: **Fast**, **Balanced**, or **Final**
- **Particle distance**, **Solver iterations**, and **Solver substeps** for quality
- **Fabric** controls for density, thickness, stretch, shear, bend, friction, color, specular, roughness and transparency
- **Avatar skin offset** and collision fallback radius when applicable
- **Step** for one controlled advancement
- **Run 30** for the normal batch action
- **Reset** to restore solver state while retaining authored quality/material values

The status area reports DrapeTarget validity. **Step** and **Run 30** are intentionally blocked for stale, unbuilt, unassigned, invalid, missing or disabled targets.

The simulation scene stores PatternPieces in its ClothPieces links, so verify that the intended pieces are actually linked before assuming the solver is missing geometry.

### 6. Diagnose and iterate

After a valid drape, use **Cloth Diagnostics** for stress/strain/fit/pressure analysis where supported by the current scenario.

When something changes upstream:

    Pattern edit
      → recompute
      → validate/repair sewing if needed
      → refresh DrapeTarget if needed
      → simulate again

Cloth intentionally fails closed on stale derived state rather than silently consuming an outdated target or seam reference.

## Current tunic behavior

The validated tunic acceptance path uses two native Sketcher PatternPieces, semantic sewing, a production mannequin/DrapeTarget, persisted quality/material settings, real simulation steps and diagnostics.

For the current acceptance fixture, authored shoulder pinning is used on the front panel while the back panel is not globally pinned. This is an acceptance fixture detail, not a general requirement that every garment be globally pinned. It also is not evidence of automatic body snapping.

Use [EXAMPLES.md](EXAMPLES.md) for the shortest tunic walkthrough and [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) for command-level details.

## Recovery checklist

**No workbench:** fix the FreeCAD Mod installation and restart.

**No pattern geometry:** edit the native Sketcher source and recompute; do not edit a legacy drafting representation for a new piece.

**Seam invalid:** validate, repair only if the existing semantic edge still exists, otherwise recreate the seam.

**Target stale:** open **Edit Drape Target** → verify source/provider → **Apply & Refresh**.

**Simulation blocked:** read the target status first. A blocked Run is usually a target-state problem, not a solver setting.

**Cloth missing:** inspect the simulation object's ClothPieces links and recompute.

**Tunic collision problem:** check explicit arrangement/placement, DrapeTarget refresh and current pin/stitch inputs before changing solver quality.

# Workbench guide

FreeCAD Cloth has three cooperating native workbenches:

- **Cloth Pattern** — author and inspect 2D pattern pieces.
- **Cloth Sewing** — create, edit and validate semantic sewing relationships, plus fitting/avatar arrangement.
- **Cloth Simulation** — create the DrapeTarget, configure quality/material state and simulate.

The public command IDs below are useful when reproducing a scenario or when a command is easier to find by its stable name.

## Pattern workbench

### New pattern piece

Use **Cloth Pattern → Create Piece** or the **Create Piece** task panel.

The PatternPiece task panel exposes:

- Piece name
- Geometry source
- Width (derived)
- Height (derived)
- Seam allowance
- Grainline angle
- **Edit native Sketch…** when the piece is Sketcher-authoritative

The authoritative authoring path is native FreeCAD Sketcher. Public command IDs include:

- ClothPattern_CreatePieceTask
- ClothPattern_CreatePiece
- ClothPattern_CreatePieceWithSketch
- ClothPattern_CreateFromSketch
- ClothPattern_EditSketch
- ClothPattern_EditPiece
- ClothPattern_Show2D
- ClothPattern_RepairTopology
- ClothPattern_Export

The former PatternDrafting polygon editor is compatibility-only for legacy documents. It is not the normal Pattern workbench authoring command.

### Production 2D export

Select a PatternPiece and run **Export Pattern** (ClothPattern_Export). The task panel produces deterministic SVG or DXF derived from the authoritative native Sketcher geometry and preserves the source document.

Exports fail closed when required native geometry or semantic seam references are missing/stale.

## Sewing workbench

### Create a seam

The normal selection contract is exact and deliberate:

1. Select a PatternPiece edge.
2. Select one edge on a second PatternPiece.
3. Run **Create Seam** (ClothSewing_CreateSeam).
4. Use the staged **Preview** action.
5. Inspect validation.
6. **Commit** or **Cancel**.

The task panel is transactional: Preview stages the normal persisted objects; Commit closes the transaction; Cancel aborts it.

Other sewing commands include:

- **Create M:N Sewing** — deterministic 1:N/M:1/M:N sewing relationships.
- **Create Sewing Network** — group canonical seam segments into a sewing network.
- **Free Sewing** — partial-edge sewing relationships.
- **Create Sewing Operation** — build the persistent operation from the selected seam.
- **Edit Sewing Operation** — edit alignment, orientation, tolerance and stitch samples.
- **Reverse Seam** / **Toggle Seam Alignment** — change correspondence behavior.
- **Validate Sewing** — report seam validity and length mismatches.
- **Repair Seam** — repair reversible or invalid-range correspondence without hiding physical mismatch.
- **Focus Seam in 3D** — isolate the selected seam and fit the view.
- **Edit Seam Side A/B in Sketcher** — open the authoritative source edge for direct correction.
- **Show Sewing 2D** — top view of pattern, seams and stitch correspondence.

### Seam colors

Seams use deterministic colors in the 2D sewing view and preserve the placed/world-space 3D presentation. Use **Show Sewing 2D** or **Focus Seam in 3D** when a seam is difficult to identify.

## Fitting and avatar

The fitting/avatar commands live in the **Cloth Sewing** workbench under **Fitting & Avatar**.

Typical sequence:

1. **Create Avatar** (ClothFitting_CreateAvatar).
2. **Edit Avatar** (ClothFitting_EditAvatar) to change Body measurements, Proportions, Avatar provider, Pose and Display.
3. **Create Fitting Scene** (ClothFitting_CreateScene).
4. Select PatternPieces and run **Add Pieces** (ClothFitting_AddPieces).
5. Create/edit **Arrangement Points** and apply one to a selected PatternPiece.
6. Use **Reset Arrangement** when needed.
7. Create the simulation from the fitting scene with **Create Simulation**.

The avatar editor has pose presets **standing**, **sewing**, and **sitting**, plus an explicit **Apply & Rebuild** action.

Arrangement points are persistent placement metadata. They are a deterministic foundation for garment placement, not a generic automatic body-snap algorithm.

## Drape Target

The DrapeTarget is the authoritative collision input for simulation.

Public commands:

- **Create Target** (ClothDrape_CreateTarget) — use the selected FreeCAD Shape/Mesh.
- **Create Mannequin Target** (ClothDrape_CreateMannequinTarget) — use the Cloth mannequin.
- **Edit Drape Target** (ClothDrape_EditTarget).
- **Refresh Drape Target** (ClothDrape_RefreshTarget).
- **Enable Target** / **Disable Target**.
- **Cloth Diagnostics** after simulation.

The target panel exposes:

- Provider: **Mannequin** / **FreeCAD Geometry**
- Source
- Collision-quality preset: **Preview**, **Normal**, **Final**
- Tessellation
- Collision thickness
- **Apply & Refresh**
- **Cancel**

**Apply & Refresh** rebuilds collision geometry. **Cancel** leaves the document unchanged.

## Simulation

Create or edit a simulation with:

- **Create Simulation** (ClothSimulation_Create)
- **Simulation Controls** (ClothSimulation_Edit)
- **Step** (ClothSimulation_Step)
- **Run 30** (ClothSimulation_Run)
- **Reset** (ClothSimulation_Reset)

The quality panel separates the authored simulation configuration into three groups:

### Simulation quality

- Preset: **Fast**, **Balanced**, **Final**
- Particle distance (mm)
- Solver iterations
- Solver substeps

### Fabric

- Density
- Thickness
- Stretch
- Shear
- Bend
- Friction
- Color
- Specular
- Roughness
- Transparency

### Collision / run

- Avatar skin offset
- Fallback sphere radius
- Simulation steps
- **Step**
- **Run 30**
- **Reset**

The status message reports target state and solver state. Run/Step is blocked when the DrapeTarget is stale, unbuilt, unassigned, invalid, missing or disabled.

## Pattern → Sewing → Arrange/Fit → Simulate example

For a compact reproducible garment flow:

1. **Pattern:** create two native Sketcher sketches and adopt them with **Create From Sketch**.
2. **Sewing:** select matching semantic edges, **Create Seam**, **Preview**, then **Commit**; create a Sewing Operation and validate it.
3. **Arrange/Fit:** create a mannequin and fitting scene, add the two PatternPieces, create arrangement points and apply them to establish persistent placements.
4. **Drape Target:** create the mannequin target and **Apply & Refresh** it.
5. **Simulate:** create the simulation scene, verify the PatternPieces are linked in ClothPieces, select a quality preset, then use **Run 30**; use **Step** for debugging and **Reset** for recovery.
6. **Inspect:** use seam focus and diagnostics before export/save.

## Persistence and invalidation

The saved FreeCAD document is authoritative. Transient GUI selection and previews are not.

After a Pattern, seam-source or target edit:

    recompute
    → inspect stale/invalid reason
    → repair semantic sewing only when the referenced identity survives
    → refresh/rebuild the DrapeTarget
    → simulate again

Do not compensate for stale state by changing generated mesh edge order or silently reassigning a seam.

## Troubleshooting

**Workbench missing:** restart FreeCAD and verify the repository is installed as a FreeCAD Mod package.

**Command disabled:** check the active document and selection. The commands intentionally reject incomplete inputs.

**Seam invalid after editing:** use **Validate Sewing**, then **Repair Seam** only when the semantic edge still exists; otherwise recreate the seam.

**Drape target stale:** open **Edit Drape Target**, verify Provider/Source, and use **Apply & Refresh**.

**Simulation blocked:** read the target status before changing solver quality. Stale collision state is intentionally fail-closed.

**Simulation has no cloth:** verify the simulation object's ClothPieces links and recompute.

**Tunic intersects the mannequin:** verify explicit arrangement/placements and target refresh first. The current release does not claim automatic CLO-style body snapping.

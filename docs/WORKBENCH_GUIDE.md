# Workbench guide

FreeCAD Cloth has three cooperating native workbenches:

- **Cloth Pattern** — author and inspect 2D pattern pieces.
- **Cloth Sewing** — create, edit and validate semantic sewing relationships, plus fitting/avatar arrangement.
- **Cloth Simulation** — create the persistent `DrapeTarget`, configure quality/material state and simulate.

The public command IDs below are the stable names registered by the current code. The visible labels are included where they are user-facing.

## Pattern workbench

### New pattern piece

Use:

- **Create Pattern Piece Task** (`ClothPattern_CreatePieceTask`)
- **Create Pattern Piece With Sketch** (`ClothPattern_CreatePiece` / `ClothPattern_CreatePieceWithSketch`)
- **Create Pattern Piece From Selected Sketch** (`ClothPattern_CreateFromSketch`)

The normal geometry authority is native FreeCAD Sketcher. **Edit Sketch** (`ClothPattern_EditSketch`) opens that authoritative geometry. **Edit Pattern Piece** (`ClothPattern_EditPiece`) edits persistent garment metadata rather than creating a second geometry model.

Other public Pattern commands include `ClothPattern_CreateGarment`, `ClothPattern_CreateSketch`, `ClothPattern_Show2D`, `ClothPattern_RepairTopology`, `ClothPattern_CreateMesh`, `ClothPattern_AddSeam`, and `ClothPattern_Export`.

### Production 2D export

Select a PatternPiece and run **Export Pattern** (`ClothPattern_Export`). The export is derived from authoritative Sketcher geometry, is deterministic for identical document state, and fails closed when required native geometry or semantic seam references are missing/stale.

## Sewing workbench

### Create and validate a seam

The normal selection contract is:

1. Select one PatternPiece edge.
2. Select one compatible edge on a second PatternPiece.
3. Run **Create Seam** (`ClothSewing_CreateSeam`).
4. Use **Preview**.
5. Inspect validation.
6. **Commit** or **Cancel**.

The other public sewing commands are:

- **Create M:N Sewing** (`ClothSewing_CreateMNSewing`) — deterministic 1:N, M:1 and M:N relationships.
- **Create Sewing Operation** (`ClothSewing_CreateOperation`).
- **Edit Sewing Operation** (`ClothSewing_EditOperation`).
- **Reverse Seam** (`ClothSewing_ReverseSeam`).
- **Toggle Seam Alignment** (`ClothSewing_ToggleAlignment`).
- **Validate Sewing** (`ClothSewing_Validate`).
- **Repair Seam** (`ClothSewing_RepairSeam`).
- **Focus Seam in 3D** (`ClothSewing_FocusSeam3D`).
- **Edit Seam Side A in Sketcher** (`ClothSewing_EditSeamSideA`).
- **Edit Seam Side B in Sketcher** (`ClothSewing_EditSeamSideB`).
- **Show Sewing 2D** (`ClothSewing_Show2D`).

### Seam presentation

Seams receive deterministic colors in the 2D sewing presentation and keep their placed/world-space 3D presentation. **Focus Seam in 3D** fits the selected semantic seam; the two Sketcher-side commands open the authoritative semantic source edge.

If a Sketcher edit invalidates a semantic edge reference, keep the seam invalid until it is explicitly repaired/recreated. Do not substitute generated mesh edge order for semantic identity.

## Fitting and avatar

The fitting/avatar commands are available from **Cloth Sewing**:

- **Create Avatar** (`ClothFitting_CreateAvatar`)
- **Create Fitting Scene** (`ClothFitting_CreateScene`)
- **Add Selected Pattern Pieces** (`ClothFitting_AddPieces`)
- **Create Arrangement Point** (`ClothFitting_CreateArrangementPoint`)
- **Set Arrangement Point** (`ClothFitting_SetArrangementPoint`)
- **Delete Arrangement Point** (`ClothFitting_DeleteArrangementPoint`)
- **Create Bounding Volume** (`ClothFitting_CreateBoundingVolume`)
- **Delete Bounding Volume** (`ClothFitting_DeleteBoundingVolume`)
- **Set Symmetry** (`ClothFitting_SetSymmetry`)
- **Apply Selected Arrangement** (`ClothFitting_ApplyArrangementPoint`)
- **Reset Arrangement** (`ClothFitting_ResetArrangement`)
- **Create Simulation from Fitting** (`ClothFitting_CreateSimulation`)

Avatar-specific commands include **Edit Avatar**, **Rebuild Avatar**, **Set Avatar Measurements**, **Set Avatar Pose**, **Set Avatar Provider**, and **Set Avatar Skin Offset**.

Arrangement points and saved piece placements are persistent fitting inputs. This guide intentionally does not promote an unvalidated general automatic body-snap workflow.

## DrapeTarget

The `DrapeTarget` is the authoritative collision input for simulation.

Public commands:

- **Create Target** (`ClothDrape_CreateTarget`) — selected FreeCAD Shape/Mesh.
- **Create Mannequin Target** (`ClothDrape_CreateMannequinTarget`) — bundled human mannequin.
- **Edit Drape Target** (`ClothDrape_EditTarget`).
- **Refresh Drape Target** (`ClothDrape_RefreshTarget`).
- **Enable Target** (`ClothDrape_EnableTarget`).
- **Disable Target** (`ClothDrape_DisableTarget`).
- **Cloth Diagnostics** (`ClothDrape_Diagnostics`).

The persistent target types are exactly **Mannequin** and **FreeCAD Geometry**. **Edit Drape Target** exposes provider/source and collision settings; **Refresh Drape Target** rebuilds the collision metadata after source changes.

Target state is explicit and user-visible: missing, disabled, invalid, unassigned, unbuilt, stale, or ready. The simulation intentionally blocks **Step** and **Run 30** when the persistent collision state is not valid/current.

## Simulation

Use:

- **Create Simulation** (`ClothSimulation_Create`)
- **Create Drape Scene** (`ClothSimulation_CreateDrape`) when a deterministic drape scene is required
- **Simulation Controls** (`ClothSimulation_Edit`)
- **Step Simulation** / **Step** (`ClothSimulation_Step`)
- **Run Simulation** / **Run 30** (`ClothSimulation_Run`)
- **Reset Simulation** / **Reset** (`ClothSimulation_Reset`)

### PinMode

The persistent `PinMode` property has exactly three values:

- **Automatic** — preserve legacy behavior; use `PinSelection` when present, otherwise the existing automatic boundary pins.
- **Explicit** — use only `PinSelection`.
- **None** — create the simulation with zero solver pins.

Pin mode and the parsed `PinSelection` are part of the deterministic simulation rebuild signature. The current task panel exposes the three modes but does not provide a mesh-vertex authoring editor for arbitrary `PinSelection` indices.

### Quality and fabric

The quality panel separates:

- Preset: **Fast**, **Balanced**, **Final**
- Particle distance
- Solver iterations
- Solver substeps
- Fabric density, thickness, stretch, shear, bend and friction
- Fabric color, specular response, roughness and transparency
- Avatar skin offset and collision radius
- Simulation steps
- **Step**, **Run 30**, **Reset**

Presentation properties are persisted separately from the physical solver parameters.

## Compact reproducible garment flow

1. **Pattern:** create two native Sketcher PatternPieces or adopt existing Sketcher objects with `ClothPattern_CreateFromSketch`.
2. **Sewing:** `ClothSewing_CreateSeam` → **Preview** → **Commit**; create and validate the Sewing Operation.
3. **Arrange/Fit:** create the avatar and fitting scene, add the PatternPieces, create/apply arrangement points, then keep the persistent placements.
4. **DrapeTarget:** create the mannequin or generic-geometry target and refresh it after source changes.
5. **Simulate:** create the simulation, verify `ClothPieces`, choose quality/material settings, then **Run 30**; use **Step** for debugging and **Reset** for recovery.
6. **Inspect:** use seam focus and supported diagnostics before export/save.

No step in this documented path assumes an unvalidated automatic target-snap behavior.

## Persistence and invalidation

The saved FreeCAD document is authoritative. Transient GUI selection and previews are not.

After a Pattern, seam-source or target edit:

```
recompute
  → inspect stale/invalid reason
  → repair semantic sewing only when the referenced identity survives
  → refresh/rebuild the DrapeTarget
  → simulate again
```

Do not compensate for stale state by changing generated mesh edge order or silently reassigning a seam.

## Troubleshooting

**Workbench missing:** restart FreeCAD and verify the repository is installed as a FreeCAD `Mod` package.

**Command disabled:** check the active document and selection. The commands intentionally reject incomplete inputs.

**Seam invalid after editing:** use **Validate Sewing**, then **Repair Seam** only when the semantic edge still exists; otherwise recreate the seam.

**DrapeTarget stale:** use **Edit Drape Target**, verify Provider/Source, and run **Refresh Drape Target**.

**Simulation blocked:** read the target status before changing solver quality. Stale collision state is intentionally fail-closed.

**Simulation has no cloth:** verify the simulation object's `ClothPieces` links and recompute.

**Tunic intersects the mannequin:** verify persistent arrangement/placements and target refresh first. The current documentation does not treat automatic body snapping as a general supported guarantee.
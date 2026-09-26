# Workbench guide

FreeCAD Cloth has three cooperating native workbenches:

- **Cloth Pattern** — create and inspect 2D PatternPieces while FreeCAD Sketcher remains the geometry authority.
- **Cloth Sewing** — create, edit, validate, and visualize semantic sewing relationships.
- **Cloth Simulation** — select cloth and collision targets, arrange/drape, simulate, reset, and inspect diagnostics.

This page is the detailed UI reference; [User guide](USER_GUIDE.md) is the shorter new-user path.

## Cloth Pattern

### Core commands

- `ClothPattern_CreateGarment` — create the production document hierarchy.
- `ClothPattern_CreatePieceTask` — open the PatternPiece creation task panel.
- `ClothPattern_CreateFromSketch` — adopt a selected native Sketcher object.
- `ClothPattern_EditPiece` — edit persistent PatternPiece metadata.
- `ClothPattern_EditSketch` — enter the linked native Sketcher source.
- `ClothPattern_CreateSketch` — create a native Sketcher representation for a selected piece.
- `ClothPattern_Show2D` — switch to a top-down pattern view.
- `ClothPattern_Export` — open deterministic SVG/DXF export for a selected piece.

The Pattern task panel shows persistent metadata such as piece name, seam allowance, and grainline angle. When a PatternPiece is Sketch-authoritative, the geometry source is shown as **Sketch** and the dimensions are derived rather than independently editable.

The legacy polygon drafting panel still exists only for explicit compatibility/migration. Normal Pattern workbench registration does not expose it as a current authoring path.

## Cloth Sewing

The workbench groups commands as **Sewing Creation**, **Sewing Editing**, **Validation & View**, and **Fitting & Avatar**.

### Create and validate seams

- **Create Seam** / `ClothSewing_CreateSeam`
- **Create M:N Sewing** / `ClothSewing_CreateMNSewing`
- **Free Sewing** / `ClothSewing_FreeSewing`
- **Create Sewing Network** / `ClothSewing_CreateNetwork`
- **Create Sewing Operation** / `ClothSewing_CreateOperation`
- **Edit Sewing Operation** / `ClothSewing_EditOperation`
- **Validate Sewing** / `ClothSewing_Validate`

Selections are validated before a seam is committed. The sewing operation panel exposes correspondence, length, reversal, ranges, and recovery controls.

### Recovery and visual inspection

- **Reverse Seam** / `ClothSewing_ReverseSeam`
- **Toggle Seam Alignment** / `ClothSewing_ToggleAlignment`
- **Repair Seam** / `ClothSewing_RepairSeam`
- **Focus Seam in 3D** / `ClothSewing_FocusSeam3D`
- **Edit Seam Side A in Sketcher** / `ClothSewing_EditSeamSideA`
- **Edit Seam Side B in Sketcher** / `ClothSewing_EditSeamSideB`
- **Show Sewing 2D** / `ClothSewing_Show2D`

The seam view applies deterministic colors by seam identity. Generated mesh order is not the identity source.

## Fitting and avatar commands

Fitting is part of the **Cloth Sewing** workbench:

- `ClothFitting_CreateScene`
- `ClothFitting_AssignAvatar`
- `ClothFitting_AddPieces`
- `ClothFitting_CreateArrangementPoint`
- `ClothFitting_ApplyArrangementPoint`
- `ClothFitting_ResetArrangement`
- `ClothFitting_CreateSimulation`

The current target-neutral collision providers are the native mannequin and ordinary FreeCAD Shape/PartDesign/Body/Mesh geometry.

## Cloth Simulation

The simulation workbench exposes:

- **Create Simulation** / `ClothSimulation_Create`
- **Simulation Controls** / `ClothSimulation_Edit`
- **Step Simulation** / `ClothSimulation_Step`
- **Run Simulation** / `ClothSimulation_Run`
- **Reset Simulation** / `ClothSimulation_Reset`
- **Create Target** / `ClothDrape_CreateTarget`
- **Create Mannequin Target** / `ClothDrape_CreateMannequinTarget`
- **Edit Drape Target** / `ClothDrape_EditTarget`
- **Refresh Drape Target** / `ClothDrape_RefreshTarget`
- **Cloth Diagnostics** / `ClothDrape_Diagnostics`

The simulation task panel currently contains these visible groups:

- **Scene** — **Cloth pieces**, **Drape target**
- **Fabric** — preset and physical fabric controls
- **Solver** — iterations, timestep, gravity, and step count
- **Drape target collision** — thickness and mesh deflection
- **Sewing & pinning** — **Pinned vertices**, **Seam pairs**

Primary controls are **Step**, **Run 30 steps**, and **Reset**. The status label reports finite-state and DrapeTarget readiness.

A target is ready only after its collision surface is current. If the source geometry, placement, collision tessellation, or collision thickness changes, the target becomes stale and must be refreshed before Run/Step.

## Document and recovery model

FreeCAD's saved `.FCStd` document is the persistence authority.

```text
Sketcher geometry
      ↓
PatternPiece / PatternMark
      ↓
PatternIR + SewingGraph
      ↓
SimulationScene + DrapeTarget
      ↓
Derived mesh / solver state
```

When upstream inputs change, derived data is rebuilt or explicitly repaired. Selection and task-panel state are transient and never replace the document model.

## Production output

The Pattern workbench's **Export Pattern** path produces deterministic SVG or DXF derived from the authoritative native Sketcher source.

Exports fail closed when required native geometry or semantic seam references are missing/stale. Repeating an export with identical document state is expected to produce byte-identical output.

## Troubleshooting summary

- Missing workbench → verify `Mod` installation, root bootstrap files, and Python/runtime compatibility.
- Disabled command → satisfy its document/selection precondition.
- Invalid seam → recompute, inspect status, then repair/remap explicitly.
- Stale DrapeTarget → refresh the target before simulation.
- Non-finite simulation → Reset and inspect target/mesh state before changing solver parameters.

See [User guide](USER_GUIDE.md#troubleshooting-and-diagnostics) for the user-facing recovery flow.

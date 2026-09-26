# User guide

This guide is the shortest supported route from a fresh installation to a saved, inspectable Cloth simulation. It uses the same document model and UI contracts exercised by the repository's acceptance tests.

## 1. First successful result: Blanket over Cube

Start with [Installation](INSTALLATION.md), then validate the workbench before building a full garment.

The **Blanket over Cube** path intentionally uses one PatternPiece and one generic FreeCAD collision target. It is the simplest way to separate cloth, collision, pinning, and solver problems from garment sewing and avatar fitting.

For the repository's canonical visual acceptance fixture, the exact executable source is `tests/freecad_visual_examples.py`. It creates a native Sketcher blanket, a FreeCAD cube collision target, two opposite boundary pins, and real motion frames. This fixture is an acceptance artifact, not a hidden one-click demo command.

For a GUI-built scene:

1. Switch to **Cloth Pattern**.
2. Create a new pattern piece with **Create Piece Task** / `ClothPattern_CreatePieceTask`.
3. In the pattern task panel, keep **Sketch** as the geometry authority or use **Edit native Sketch…** to enter FreeCAD Sketcher.
4. Give the piece a simple rectangular outline and recompute.
5. Switch to a standard FreeCAD workbench and create a cube/box to act as collision geometry.
6. Switch to **Cloth Simulation** and choose **Create Simulation** / `ClothSimulation_Create`.
7. Assign the PatternPiece under **Cloth pieces** and create a persistent drape target from the selected FreeCAD shape with **Create Target** / `ClothDrape_CreateTarget`.
8. The Simulation panel exposes **Scene**, **Fabric**, **Solver**, **Drape target collision**, and **Sewing & pinning** sections. Pins are entered as particle indices in **Pinned vertices**; seam stitch pairs use **Seam pairs**.
9. Run a small batch with **Run 30 steps** or advance one frame with **Step**. Use **Reset** to return to the authored setup without clearing selections.
10. A healthy target reports **Drape target collision surface is current**. A stale target must be rebuilt before **Run** or **Step**.

The canonical visual fixture derives the blanket's opposite-corner particle IDs from the generated mesh instead of asking the user to guess particle numbers. That is why the repository acceptance example is more deterministic than a manual pin-entry workflow.

## 2. Standard garment workflow

The normal garment journey is:

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

### Pattern

Use native FreeCAD Sketcher as the editable geometry authority.

Typical commands:

- `ClothPattern_CreateGarment` — create the production garment document hierarchy.
- `ClothPattern_CreatePieceTask` — create a PatternPiece through the task panel.
- `ClothPattern_CreateFromSketch` — adopt a selected native Sketcher object without creating a competing geometry editor.
- `ClothPattern_EditPiece` — edit persistent PatternPiece metadata.
- `ClothPattern_EditSketch` — enter the linked native Sketcher source.
- `ClothPattern_Export` — open deterministic SVG/DXF production export for a selected PatternPiece.

Pattern geometry remains owned by Sketcher. Do not treat generated mesh edges or derived seam-allowance geometry as the persistent pattern authority.

### Sewing

Switch to **Cloth Sewing** and create explicit semantic relationships from compatible edges.

The basic command path is:

1. Select one edge on each of two PatternPieces.
2. Use **Create Seam** / `ClothSewing_CreateSeam`.
3. Review orientation, correspondence, and length status in the sewing task panel.
4. Use **Create Sewing Operation** / `ClothSewing_CreateOperation` when a persistent sewing-operation object is needed.
5. Use **Validate Sewing** / `ClothSewing_Validate` before fitting or simulation.
6. For multi-edge relationships, use **Free Sewing**, **Create M:N Sewing**, or **Create Sewing Network** as appropriate.

For recovery:

- **Reverse Seam** changes B-side correspondence.
- **Toggle Seam Alignment** switches endpoint/uniform alignment.
- **Repair Seam** performs only explicit semantic/reference repairs; it does not hide a physical length mismatch.
- **Focus Seam in 3D** isolates the selected semantic seam in the 3D view.
- **Edit Seam Side A/B in Sketcher** opens the authoritative native Sketcher edge.

Seam colors are deterministic and tied to seam identity, not generated mesh edge order.

### Arrange/Fit

Use **Cloth Sewing** for fitting/arrangement commands.

A typical sequence is:

1. **Create Fitting Scene** / `ClothFitting_CreateScene`.
2. **Assign Avatar Source** / `ClothFitting_AssignAvatar` when using the native mannequin.
3. **Add Pieces** / `ClothFitting_AddPieces` to the fitting scene.
4. Create or use arrangement points and apply them to each piece with **Apply Arrangement Point** / `ClothFitting_ApplyArrangementPoint`.
5. Use **Reset Arrangement** / `ClothFitting_ResetArrangement` when you need to return all assigned pieces to their saved pre-arrangement placement.
6. **Create Simulation** / `ClothFitting_CreateSimulation` to carry the fitting scene into Cloth Simulation.

A `DrapeTarget` can be a native human mannequin or ordinary FreeCAD Shape/PartDesign/Body/Mesh geometry. The target contract is target-neutral; the solver consumes the collision surface derived from it.

### Simulate

In **Cloth Simulation**:

1. Confirm the correct **Cloth pieces** and **Drape target**.
2. Confirm the target status is current.
3. Choose a fabric preset or adjust physical material values.
4. Use the solver controls only when needed for iteration/debugging.
5. Run the simulation with **Run Simulation** / `ClothSimulation_Run`, advance one step with **Step Simulation** / `ClothSimulation_Step`, or restore the authored state with **Reset Simulation** / `ClothSimulation_Reset`.
6. Inspect the result before export or saving a final document.

The task panel separates physical solver values from persisted fabric presentation. Color, roughness, specular response, and transparency are presentation controls; they do not replace physical material parameters.

### Diagnose

Use **Cloth Diagnostics** / `ClothDrape_Diagnostics` after a simulation when you need structured diagnostic output. A diagnostic view is evidence about the current simulation; it is not a second persistence or solver model.

### Output

The current production 2D export path is **Export Pattern** / `ClothPattern_Export` from a selected PatternPiece. SVG and DXF are derived from authoritative native Sketcher geometry. Export is fail-closed when required geometry or semantic references are missing or stale.

## 3. Recovery and stale-state rules

Cloth deliberately refuses to silently consume outdated derived data.

When something is invalid, use this sequence:

1. **Recompute** the FreeCAD document.
2. Read the displayed status/reason.
3. Repair the semantic object or refresh the affected derived state.
4. Run again only after the target/scene reports a current, finite state.

Important examples:

- A changed DrapeTarget must be rebuilt before simulation.
- A deleted, split, or merged Sketch edge can invalidate a seam; repair or recreate the semantic reference explicitly.
- A non-finite simulation state should be reset rather than treated as valid output.
- A disabled or missing DrapeTarget is a blocker, not a warning that can be ignored.

## Troubleshooting and diagnostics

**The workbench is missing**

See [Installation](INSTALLATION.md). The repository must be directly below FreeCAD's user `Mod` directory, and FreeCAD must be restarted after installation.

**The command is greyed out**

Most commands have explicit activation guards. Check the active document and selection requirements instead of forcing the command through the Python console.

**A seam is invalid after a Sketch edit**

Recompute. Validate the seam. If the semantic edge still exists, use **Repair Seam**; otherwise recreate the seam against the intended edge.

**Sewing correspondence is reversed or ranges are wrong**

Use **Reverse Seam**, **Toggle Seam Alignment**, **Reset Ranges**, or the sewing operation's repair controls. A real length mismatch must be addressed in the pattern/seam ranges; increasing a tolerance is not a substitute for correcting geometry.

**The target status is stale**

Use **Edit Drape Target** to inspect the target, then **Refresh Drape Target** / `ClothDrape_RefreshTarget`. Target signatures include source geometry/mesh, placement, tessellation, and collision thickness.

**The simulation looks wrong**

Use **Reset** and check the DrapeTarget before changing solver parameters. For avatar scenes, verify the garment is arranged around the target before running the solver.

**A local result differs from the published examples**

The published README/example media is generated by the canonical workflow. Match the validated runtime versions first, then compare the generated logs and images. Do not hand-edit published evidence.

## 4. Capability boundary

The current release is intentionally narrower than a commercial garment suite.

Implemented and documented on current `main` include native Sketcher-backed PatternPieces, semantic seams and sewing networks, target-neutral mannequin/FreeCAD geometry collision, fitting/arrangement state, deterministic CPU simulation, persisted fabric presentation controls, diagnostics, and SVG/DXF pattern export.

The following remain roadmap work and should not be described as complete merely because the tunic path passes: **grading/nesting, construction hardware, richer avatar posing, pressure/fit maps, and calibration-grade material libraries**. See [Release gates](RELEASE_GATES.md) and [Roadmap](../ROADMAP.md).

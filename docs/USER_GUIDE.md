# User guide

This is the shortest path from an installed workbench to a complete garment workflow.

## Start with a known-good first result

Before testing a full garment, run the [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube) example.

It deliberately uses one pattern, one generic FreeCAD collision target and explicit pins. When the blanket reaches the cube without exploding, detaching or penetrating badly, the installation and basic simulation path are working.

Use the [Tunic](EXAMPLES.md#2-tunic) only after the basic example succeeds.

## The normal garment loop

**Pattern → Sewing → Fitting → Pose → Simulation → Diagnosis → Edit → Rebuild**

### 1. Pattern — create the authoritative 2D source

Open **Cloth Pattern**.

Create or open a native Sketcher sketch and turn it into a PatternPiece. Use Sketcher for dimensions, constraints and curves. Cloth adds garment meaning such as semantic piece identity, seam references, seam allowance, grainline, notches and internal marks.

A pattern can also start with **Cloth Pattern → 3D Pattern Pen** for the bounded planar-extraction workflow. The resulting PatternPiece is still a normal Sketcher-backed object.

**Done when:** the pieces are visible in the document, editable in Sketcher and valid after recompute.

### 2. Sewing — describe how pieces belong together

Open **Cloth Sewing**.

Select compatible semantic edges or ranges, review direction/reversal and correspondence, then commit the seam. The seam relationship is persistent; generated mesh topology is not.

**Done when:** the intended edges highlight consistently and the sewing view reports no unresolved reference or correspondence error.

### 3. Fitting — put pieces around the target

Create or select a **DrapeTarget**.

Targets can come from the native mannequin or supported FreeCAD geometry. Arrange pieces in the 3D view using the available placement/arrangement interactions. Persistent fitting state belongs to the document.

**Done when:** the pieces are arranged where you expect them before simulation begins.

### 4. Pose — change the mannequin when needed

Use mannequin Pose Mode for joint rotations and symmetry. Treat the pose as document state; the displayed deformed body is derived from it.

**Done when:** the mannequin has the intended persistent pose and its downstream target state is current.

### 5. Simulate — create derived cloth state

Open **Cloth Simulation** and confirm the target is valid/current, quality and material settings are appropriate, pins/stitches are intentional, and there is no stale derived state.

Use **Run** for the normal workflow, **Step** for controlled investigation and **Reset** for recovery.

**Done when:** the simulation reaches a stable cloth state and the garment remains coherent from more than one view.

### 6. Diagnose — inspect before exporting

Inspect the final garment from multiple sides and use the diagnostic view when available.

Look for penetration, detached seams, implausible rigid-sheet behavior, collapsed geometry and unexpected topology changes.

**Done when:** the result is visually plausible and the relevant diagnostics are current.

## What persists and what does not

The saved FreeCAD document is authoritative.

**Persistent:** Sketcher geometry, PatternPiece semantics, semantic seam records, fitting state, pose, target identity, material/quality inputs and other documented object properties.

**Derived:** simulation meshes, particles, constraints, collision acceleration data and solver runtime state.

**Transient:** selection highlights, drag previews and other viewport-only interaction state.

Changing an upstream authoritative input should invalidate affected derived state rather than silently reusing it.

## Recovery first

| Symptom | First action |
| --- | --- |
| Workbench or command is missing | Use [Troubleshooting](TROUBLESHOOTING.md) and verify the installation path |
| Seam becomes invalid after a sketch edit | Recompute, inspect the reported reference and repair/recreate the seam explicitly |
| Arrangement looks wrong | Reset/rearrange before running the solver |
| Simulation is stale | Refresh/rebuild the target or derived scene, then Run again |
| Simulation collapses or penetrates | Stop at the first failing visual state and inspect [simulation review](SIMULATION_REVIEW.md) |
| Local CI differs from canonical evidence | Compare the exact FreeCAD/solver environment recorded by the canonical workflow |

For detailed command behavior, use the [Workbench guide](WORKBENCH_GUIDE.md). For feature-by-feature visual evidence, use the [visual wiki](wiki/README.md).

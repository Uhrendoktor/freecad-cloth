# User guide

This is the canonical human-facing path after installation:

**Installation → Blanket over Cube → Pattern → Sewing → Arrange/Fit → Simulate → Recovery → Tunic**

Use the linked examples first, then use the workbench guide when you need detailed command or property behavior.

## 1. Installation

Complete [Installation](INSTALLATION.md) first. Restart FreeCAD after copying the workbench into the user `Mod` directory, then select **Cloth Pattern**, **Cloth Sewing**, or **Cloth Simulation** from the workbench selector.

## 2. Blanket over Cube

Run the [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube) example before building a garment. Pin two blanket corners, run the simulation, and verify that the cloth moves toward and around the cube.

![Blanket over cube motion](https://github.com/Uhrendoktor/freecad-cloth/raw/f276d1f5f51eb4d3d9ade58aa28c8fffd3fbc7d5/docs/images/generated/cloth-blanket-motion.gif)

This example deliberately isolates cloth, collision and pinning. If it does not behave as described, use the recovery steps below before moving to the tunic.

## 3. Pattern

In **Cloth Pattern**, create or open a native Sketcher pattern and turn it into a PatternPiece. Keep Sketcher as the editable geometry authority. Add seam allowance, notches, grainline and internal-mark metadata as needed, then recompute and validate before sewing.

For the detailed authoring sequence and export behavior, see [Workbench guide — Pattern](WORKBENCH_GUIDE.md#1-pattern). The normal authoring path is Sketcher-backed; the former polygon drafting editor is compatibility-only.

## 4. Sewing

In **Cloth Sewing**, select compatible semantic pattern edges and explicitly create the seam or M:N/free sewing relationship. Review direction, correspondence and length diagnostics before committing.

If a Sketcher edit invalidates a seam reference, leave the seam invalid until it is explicitly repaired or recreated. Do not rely on generated mesh edge order.

See [Workbench guide — Sewing](WORKBENCH_GUIDE.md#2-sewing) for staged Preview/Commit/Cancel behavior and seam inspection.

## 5. Arrange / Fit

In **Cloth Simulation**, create or select a `DrapeTarget`: either the native human mannequin or supported generic FreeCAD Shape/PartDesign/Body/Mesh geometry. Arrange the pattern pieces using their persistent placements/arrangement metadata.

Use the [arranged cloth turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/f276d1f5f51eb4d3d9ade58aa28c8fffd3fbc7d5/docs/images/generated/cloth-simulation-arranged-turntable.gif) as the visual reference for this pre-simulation state.

The arrange/reset operations prepare fitting state; they are not solver state. In the Simulation task panel, **Snap assigned pieces to target** uses the current DrapeTarget collision surface, fails closed for stale/ambiguous targets or excessive movement, and keeps the saved HomePlacements available through **Reset arrangement**.

## 6. Simulate

Generate the preview/final mesh, choose material and quality, confirm the target is valid, then choose the explicit pinning mode when needed: **Automatic** preserves legacy automatic pins, **Explicit** uses only authored PinSelection values, and **None** creates a solver with zero pins. The canonical mannequin tunic acceptance uses **None** and separately verifies step-0 target clearance. Use **Run** for normal advancement, **Step** for controlled/debug advancement, and **Reset** to recover simulation state.

Inspect the result and diagnostics before export or saving a final document. The draped turntable and tunic render below are stable examples of the published output.

![Draped cloth turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/f276d1f5f51eb4d3d9ade58aa28c8fffd3fbc7d5/docs/images/generated/cloth-simulation-draped-turntable.gif)

## 7. Recovery

After a pattern, seam or target edit:

1. Recompute the document.
2. Inspect the stale or invalid reason shown by Cloth.
3. Refresh or rebuild the affected derived state.
4. Re-run the simulation only after the target/scene reports valid state.

Typical recovery cases are documented in [Workbench guide — Troubleshooting](WORKBENCH_GUIDE.md#troubleshooting):

- **Workbench missing:** verify the workbench is installed as a FreeCAD `Mod` package, then restart FreeCAD.
- **Command disabled:** check the active document and selection; incomplete inputs are intentionally rejected.
- **Seam invalid after editing:** recompute and validate, then repair the semantic reference explicitly.
- **Simulation stale:** inspect target/scene status, refresh the target or regenerate the derived mesh, then run again.

## 8. Tunic

After the basic path is working, use the [Tunic](EXAMPLES.md#2-tunic) scenario for the full garment acceptance path: multiple native pattern pieces, semantic sewing, mannequin collision, material/quality controls, diagnostics, save/reload and invalidation.

![Tunic validation](https://github.com/Uhrendoktor/freecad-cloth/raw/f276d1f5f51eb4d3d9ade58aa28c8fffd3fbc7d5/docs/images/generated/cloth-simulation-draped-front.png)

The tunic is an acceptance scenario, not a substitute for the blanket smoke test when diagnosing a local installation.

For the detailed garment object hierarchy and end-to-end workbench sequence, continue with the [Workbench guide](WORKBENCH_GUIDE.md).

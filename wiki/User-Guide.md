# User Guide

## The complete garment path

<pre>Create / edit pattern
       ↓
Create seams
       ↓
Arrange or fit
       ↓
Select DrapeTarget
       ↓
Choose material and quality
       ↓
Run
       ↓
Inspect diagnostics
       ↓
Export / save</pre>

## 1. Create the pattern

Use **Cloth Pattern** with native Sketcher geometry.

Pattern pieces retain semantic information such as piece identity, edge identity, seam allowance, grainline and marks. Sketcher remains the editable geometry authority.

## 2. Sew the pieces

Use **Cloth Sewing** to select matching semantic edges and create seams.

Seams are semantic relationships, not mesh-edge guesses. If an upstream sketch edge is deleted, split or merged, the dependent seam can become invalid and should be repaired explicitly.

## 3. Arrange and fit

Prepare the garment around a mannequin or another supported FreeCAD target.

The project uses a persistent, solver-neutral **DrapeTarget** abstraction so a human mannequin and generic FreeCAD geometry can participate in the same simulation workflow.

## 4. Simulate

In **Cloth Simulation**:

- verify the target is current;
- rebuild stale derived state when requested;
- choose quality and resolution plus fabric parameters;
- choose pins or stitches;
- run or step the solver.

**Run** is the primary action. **Step** is useful for controlled debugging. **Reset** is recovery.

## 5. Inspect

Do not stop at the viewport.

Check diagnostics for:

- invalid pattern topology;
- invalid seam ranges or correspondence;
- missing marks;
- target penetration or stale collision state;
- solver instability.

## Persistence

Native FreeCAD document data is the project authority. Derived simulation data is rebuildable.

When a pattern, seam source or target changes, expect dependent derived state to become stale. That is intentional: the workbench avoids silently using outdated geometry.

<details>
<summary><strong>Quick recovery checklist</strong></summary>

1. Recompute the document.
2. Repair or rebuild the affected derived state.
3. Verify the DrapeTarget is current.
4. Re-check seams before running again.
5. Re-run the simulation only after the diagnostics are clean.

</details>

![Draped cloth](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif)

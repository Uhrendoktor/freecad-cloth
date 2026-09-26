# User guide

## 1. First run: prove the installation

After installation, select **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** from the FreeCAD workbench selector.

Run **Blanket over Cube** first. It is the small physics smoke test: a simple native pattern, a persistent FreeCAD collision target, explicit pins, gravity, and cloth motion. A successful run should visibly move the blanket toward and around the cube.

Once that works, continue to the garment path below.

## 2. Minimal Pattern → Sewing → Arrange/Fit → Simulate path

### Pattern

1. Work in **Cloth Pattern**.
2. Create or adopt a native Sketcher pattern piece. Native Sketcher geometry is the editable geometry authority.
3. For a production garment, use the public **Create Garment** path when you want the native `Garment` hierarchy; standalone pattern-piece creation remains supported.
4. Recompute before moving to sewing.

The important user rule is that Cloth stores garment meaning around the Sketcher source; do not treat generated mesh edges as permanent semantic identities.

### Sewing

1. Select compatible pattern edges.
2. In **Cloth Sewing**, use **Create Seam** for a pairwise seam or the supported M:N sewing command for multi-side correspondence.
3. Validate direction, correspondence, and length diagnostics before committing the relationship.
4. Recompute and inspect the result.

For inspection, **Show Sewing 2D** displays the pattern/seam correspondence. **Focus Seam in 3D** fits the selected semantic seam in world space.

### Arrange/Fit

1. In the fitting/simulation workflow, create or select a persistent `DrapeTarget`.
2. For a mannequin workflow, use the **Cloth Human Avatar** as the target. Generic supported FreeCAD Shape/PartDesign/Body/Mesh geometry can also be used as a target.
3. Add the garment pieces to the fitting scene and use their persistent placements/arrangement metadata to put the pieces around the target.
4. Treat arrangement changes as fitting state, not as a substitute for solver recovery. Resetting arrangement does not reset numerical simulation state.

The current release documents persistent fitting/arrangement and target validity. It does not promise automatic commercial-style garment-to-body snapping for every garment.

### Simulate

1. Open **Simulation Controls**.
2. Confirm the `DrapeTarget` is in a ready state.
3. Choose a quality preset: **Fast**, **Balanced**, or **Final**.
4. Adjust the **Fabric** and **Collision** values only when the garment needs different physical or presentation behavior.
5. Use **Step** for controlled debugging or **Run 30** for a normal short advance.
6. Use **Reset** to return numerical state to the starting condition while retaining authored quality/material values.
7. Inspect the result and diagnostics before saving/exporting.

The solver state is derived from the persistent document model. Pattern, seam, target, quality, material, or collision changes may invalidate downstream state and must be rebuilt or refreshed before simulation resumes.

## 3. Mannequin/tunic workflow

The tunic is the advanced example, not the installation smoke test.

A practical sequence is:

1. Create/open the garment and its native Sketcher pattern pieces.
2. Create the semantic seams in **Cloth Sewing** and validate them.
3. Switch to **Cloth Simulation** and create or select the mannequin target.
4. Use **Cloth Human Avatar** / the persistent `DrapeTarget` and arrange the garment pieces before simulation.
5. Open **Simulation Controls** and verify target status before pressing **Run 30**.
6. During inspection, use seam focus/2D inspection and the simulation diagnostics before deciding whether a problem is pattern, sewing, fitting, collision, or solver state.
7. Save/reload before treating the result as a persistent garment state.

Do not copy the internal details of the canonical CI fixture—such as test-only coordinates or authored pin indices—into a general user recipe. The fixture is executable evidence; this guide describes the supported user workflow.

## 4. Seam inspection

Seam identity is semantic and deterministic. In **Cloth Sewing**:

- **Show Sewing 2D** gives a top-view inspection of pattern/seam/stitch correspondence.
- **Focus Seam in 3D** centers the selected seam in the assembled world-space result.
- **Edit Seam Side A in Sketcher** and **Edit Seam Side B in Sketcher** open the authoritative native Sketcher sources.
- **Repair Seam** is the explicit repair path for supported invalid correspondence.

These tools are deliberately preferred over inspecting solver mesh-edge order.

## 5. Simulation controls

The **Simulation Controls** task panel is organized around the following states:

- **Simulation quality** — **Fast**, **Balanced**, **Final**, particle distance, solver iterations, and substeps.
- **Fabric** — density, thickness, stretch, shear, bend, friction, color, specular response, roughness, and transparency.
- **Collision** — avatar skin offset and fallback collision radius.
- **Run** — simulation-step count plus **Step**, **Run 30**, and **Reset**.

**Step** is useful for diagnosing a single state transition. **Run 30** advances the normal short simulation batch. **Reset** removes derived numerical progress but retains the authored quality/fabric settings.

## 6. Recovery from stale or invalid state

Use the state shown in the task panel instead of guessing.

**Target is stale/unbuilt**

Refresh the target with **Refresh Drape Target**, recompute, and wait for a ready target status before running.

**Target is missing/disabled**

Create/select the intended target and enable it, then refresh if its source geometry changed.

**Simulation is blocked**

Do not bypass a disabled **Step** or **Run 30** button. The disabled state is a fail-closed dependency check. Repair the target/derived state first.

**Seam is invalid after a Sketch edit**

Recompute, use **Repair Seam** where applicable, or recreate the seam from the authoritative Sketcher edges.

**Arrangement is wrong**

Reset the arrangement and reapply the persistent fitting/placement state before changing solver parameters.

**Simulation result is non-finite or otherwise unusable**

Use **Reset**, inspect target validity, refresh/rebuild dependent derived state, then step again. Keep the failing state and CI log when reporting a reproducible problem.

## 7. Saving and evidence

The FreeCAD document is the persistence authority. Transient GUI selection and viewport previews are not.

For repository evidence and reproducible examples, see [EXAMPLES.md](EXAMPLES.md). Generated images/logs live under `docs/images/generated/` during canonical validation; stable README media is published to the `docs/screenshots` branch.

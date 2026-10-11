# User guide: build and inspect a garment

This guide follows one garment from editable 2D source to a draped 3D result. It assumes FreeCAD Cloth is installed and a FreeCAD document is open. For the manual-install directory and Python-runtime requirements, see [Installation](INSTALLATION.md).

For your first complete garment, follow the tunic workflow below. Keep [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube) as a separate diagnostic exercise when you need to isolate the basic drape, pinning, or collision path.

## The complete workflow

**Pattern → Sewing → Fitting → Pose (optional) → Simulation → Diagnosis → Edit → Rebuild**

The screenshots and recordings are optional visual aids. Each procedure below describes the required action and the result to verify without relying on animation.

## 0. Create or import an avatar

The simplest supported human target is the bundled MakeHuman mannequin.

1. Switch the workbench selector to **Cloth Simulation**.
2. Choose **Avatar & Fitting → Create Avatar** to create the mannequin. Use **Edit Avatar** for body measurements or **Pose Avatar** to pose it. The same commands remain available under **Cloth Sewing → Fitting & Avatar** for existing users.
3. For an existing 3D body, use FreeCAD’s **File → Import** to bring a supported model into the document. Select the imported object in the tree or viewport, open **Avatar & Fitting → Edit Avatar**, choose **FreeCAD geometry**, press **Use selected FreeCAD object**, then **Apply & Rebuild**.

**Important limitation:** the FreeCAD-geometry provider consumes the imported surface as geometry; it does not import or retarget an external skeleton, skin weights, or animation. Use the bundled MakeHuman provider for the current interactive joint posing and mannequin landmarks. A generic imported surface can be used as collision/fitting geometry, but it is not equivalent to a rigged human avatar.

## 1. Create the 2D pattern source

In the **Cloth Pattern** workbench, author the outline in native Sketcher geometry or open an existing Sketcher sketch. Create a PatternPiece from that sketch; add garment metadata such as grainline, notches, internal marks, or seam allowance when needed.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Cloth Pattern workbench showing an editable Sketcher-backed garment pattern and construction marks" width="820"></p>

1. Create or open a FreeCAD document.
2. Create a Sketcher sketch with the intended closed garment outline. Use Sketcher dimensions and constraints for edits.
3. In **Cloth Pattern**, use the command that creates a PatternPiece from the selected sketch.
4. Add the construction metadata needed for your piece, then recompute the document.
5. Save the document before moving to sewing.

**Verify the result:** the piece has a clear outline, the source remains editable in Sketcher, and recompute does not leave it invalid. Use the [Pattern guide](wiki/01-pattern.md) for 3D Pattern Pen limits and export details.

## 2. Create semantic seams

Open **Cloth Sewing** and define how the pieces connect. A seam is tied to persistent piece/edge identity, not to generated mesh-edge numbering.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/seam-assignment.gif" alt="Choosing a first pattern edge, selecting its counterpart, reviewing the seam preview, and committing the relationship" width="820"></p>

1. Make sure the intended PatternPieces exist and their mating edges are visible.
2. Start **Create Seam** and choose **Pick edges in viewport**; native edge selection remains available as an alternative.
3. Select the first edge (side A), then select the mating edge on a different PatternPiece (side B).
4. Review the seam preview, direction marks, A/B labels, and any length or correspondence warning.
5. Commit only when both sides match the intended construction. Cancel and reselect when the preview is wrong.

**Verify the result:** the intended sides carry the same seam identity and direction is correct. If an edit invalidates a reference, recompute and repair or recreate it explicitly; do not select a replacement edge based only on screen position. See [Sewing](wiki/02-sewing.md).

## 3. Arrange the garment around a target

In **Cloth Simulation**, create or select a valid **DrapeTarget**. The target can be the native mannequin or supported FreeCAD geometry such as a Shape, Body, or mesh.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.gif" alt="Dragging the tunic front and back panels onto their mannequin snap points and releasing to commit both placements" width="820"></p>

1. Confirm that the intended PatternPieces and seam relationships are present.
2. Create or select the target that the cloth will collide against.
3. Open **Interactive Arrange** and select the piece to move.
4. Drag the piece in the viewport. When snapping is enabled, approach an arrangement point and wait for the snap marker before releasing.
5. Inspect the placement and use the arrangement reset/recovery action before simulation if pieces overlap unexpectedly.

**Verify the result:** every piece is placed intentionally around or near the target, and its placement is saved rather than existing only as a drag preview. See [Fitting](wiki/03-fitting.md).

## 4. Pose the mannequin (optional)

Use Pose Mode when the garment needs a different body position. You can skip this step when working with a generic FreeCAD target or when the default mannequin pose is suitable.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/pose-joint-rotation.gif" alt="Selecting a mannequin joint and editing its rotation in Pose Mode" width="820"></p>

1. Open Pose Mode for the mannequin.
2. Choose **T-pose** for near-horizontal arms and easier proportion/placement inspection, **Standing** for the normal relaxed stance, **Sewing** for a raised-arm working pose, or **Sitting** for seated fit exploration.
3. Select the joint in the viewport and drag its rotation gizmo. Enable **Mirror** or **5° Snap** only when those constraints match the intended pose.
4. Use **Joint list** or **Exact angles** for crowded views or precise values.
5. Apply and rebuild the pose; use Cancel when the staged edit should be discarded.

**Verify the result:** the mannequin shows the intended pose after the edit is applied and remains correct after saving/reopening the FCStd document. The T-pose is a fitting baseline, not a claim that imported geometry has become rigged. Rebuild target-dependent state before simulation. See [Pose Mode](wiki/04-pose.md).

## 5. Run the cloth simulation

Before running the solver, confirm that the fitting target is valid/current and that pinning, sewing constraints, material, and quality settings are intentional.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-tunic-mannequin-motion.gif" alt="Tunic motion and draping sequence as the cloth settles on the mannequin" width="820"></p>

1. Open **Cloth Simulation** and confirm the displayed target identity and validity.
2. Choose the simulation quality/resolution and fabric material settings.
3. Review the pinning mode: **Automatic**, **Explicit**, or **None**. Confirm that the selected pins and seam constraints match the intended setup.
4. Use **Run** for the normal simulation. Use **Step** only when investigating a particular state; use **Reset** to recover.
5. Watch for contact, fold development, unstable motion, and stale-state warnings. Rebuild when an upstream pattern, seam, fitting, pose, or target change invalidates the scene.

**Verify the result:** simulation state advances beyond the initial arrangement, the garment remains connected, and the result does not show severe penetration, explosion, collapse, or implausible rigid-sheet behavior. A camera rotation alone is not evidence of simulated motion. See [Simulation](wiki/05-simulation.md).

## 6. Inspect before exporting

A single attractive camera angle can hide collision penetration, a detached panel, or inverted geometry. Use multiple views and current diagnostics before deciding that a result is acceptable.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-diagnostics.png" alt="Draped garment with diagnostic visualization for inspecting cloth behavior" width="820"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png" alt="Front view of the draped garment for a six-side geometry review" width="260"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-rear.png" alt="Rear view of the draped garment for a six-side geometry review" width="260"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-left.png" alt="Left-side view of the draped garment for a six-side geometry review" width="260"></p>

1. Inspect the front, rear, left, right, top, and bottom views from the same saved result.
2. Check for penetration, detached seams or panels, collapsed geometry, unexpected topology changes, and implausible hems or openings.
3. Inspect stress or other diagnostic overlays only when the simulation and target are current.
4. Save the document and export from authoritative pattern geometry when needed.

**Verify the result:** the garment remains a coherent object from multiple angles and all diagnostic views describe the same current state. See [Diagnostics](wiki/06-diagnostics.md) and the [simulation review guide](SIMULATION_REVIEW.md).

## What is saved

The saved FreeCAD document is authoritative.

- **Persistent:** Sketcher geometry, PatternPiece identity and metadata, semantic seam records, arrangement/fitting state, mannequin pose, target identity, and documented material/quality/pinning inputs.
- **Derived:** generated simulation mesh, solver particles and constraints, and collision acceleration data.
- **Transient:** selection highlights, hover labels, and in-progress drag previews.

A change to an authoritative input can invalidate dependent derived state. Refresh or rebuild that state rather than bypassing a stale guard. See the [data model](wiki/07-data-model.md).

## Recovery guide

| Symptom | First action |
| --- | --- |
| Workbench or command is missing | Verify the Mod installation and restart FreeCAD; see [Troubleshooting](TROUBLESHOOTING.md). |
| A seam becomes invalid after editing a sketch | Recompute, inspect the reported reference, then repair or recreate the seam explicitly. |
| Pieces are badly arranged | Reset/rearrange before attempting to tune simulation settings. |
| The target or simulation is stale | Refresh/rebuild the affected target or derived scene, then run again. |
| Simulation explodes, collapses, or penetrates | Stop at the first invalid state and follow [Simulation review](SIMULATION_REVIEW.md). |
| Local visuals disagree with published evidence | Compare the source commit and the canonical FreeCAD/solver environment; do not hand-edit screenshots. |

## Next steps

- [Feature-by-feature visual wiki](wiki/README.md)
- [Examples](EXAMPLES.md)
- [Workbench command guide](WORKBENCH_GUIDE.md)
- [Troubleshooting](TROUBLESHOOTING.md)

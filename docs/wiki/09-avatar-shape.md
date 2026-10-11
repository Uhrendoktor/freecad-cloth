# 09 · Avatar shape and dimensions

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-shape-editor.png" alt="Edit Avatar task panel showing body-shape controls, numeric measurements, and transient 3D dimension handles around the mannequin" width="900"></p>

Use this editor to prepare a mannequin for pattern fitting and sewing. It separates broad body-shape controls from named, millimetre-based measurements, and keeps the viewport as the primary place to discover and adjust dimensions.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-shape-edit.gif" alt="Changing the feminine-to-masculine body-shape blend and breast fullness, then applying and rebuilding the mannequin" width="900"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-dimension-drag.gif" alt="Dragging the mannequin waist circumference handle to stage a new measurement, then applying and rebuilding the body" width="900"></p>

## Compare example body shapes

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-body-shape-gallery.png" alt="Seven real FreeCAD HM08 mannequin renders showing feminine, masculine, slim, plus-size, muscular, tall, and petite example body shapes at a shared orthographic scale" width="1000"></p>

The gallery is rendered from the bundled HM08 mannequin mesh using the existing **Gender blend**, **Breast fullness**, and measurement inputs. Camera scale stays fixed across all seven views, so body height and breadth remain comparable. Each card shows its height, waist, hip, and shape-control values.

These are **example parameter combinations**, not named presets available in a preset menu. To create a similar silhouette, enter the displayed blend/fullness values, then adjust height, chest, waist, hip, shoulder, upper-arm, and thigh measurements to the intended wearer. Use the measurements as a starting point rather than assuming the example proportions fit every person or garment.

## Prepare a mannequin for sewing

Before you start, open a document that contains the built-in MakeHuman mannequin. For the current procedural shape controls, select that provider rather than an imported FreeCAD surface.

1. In **Cloth Simulation**, choose **Avatar & Fitting → Edit Avatar**. The same editor is available under **Cloth Sewing → Fitting & Avatar** for existing workflows.
2. In **Body shape**, adjust **Gender blend** from feminine through neutral to masculine. This is a normalized body-proportion control, not a statement about a person's gender identity. Adjust **Breast fullness** separately to add front projection.
3. Keep **3D Dimensions** enabled. In the viewport, identify the labelled handles for height, shoulder breadth, chest, waist, and hip. The chest, waist, and hip rings indicate circumference; drag the corresponding handle to stage a new measurement.
4. Use the numeric **Body measurements** and **Proportions** fields when you need a precise target value. They remain available as a fallback to direct manipulation.
5. Review all staged values, then select **Apply & Rebuild**. The mannequin mesh and its derived fitting landmarks are regenerated using the committed values. Choose **Cancel** instead when the staged edits should be discarded.

## Verify the fit inputs

After rebuilding, confirm that the document's avatar properties contain the intended shape and dimensions. Save the document, close and reopen it, and verify the mannequin again before using it for fitting.

Use at least the front, rear, and side views. Check that the silhouette reflects the selected shape, the height is correct, and the named chest/bust, underbust, waist, and hip measurements match the intended sewing size. Breast fullness and bust circumference are different controls: use the circumference for garment sizing and the shape control for additional projection.

For a small end-to-end exercise, follow [Example 3: Prepare a mannequin for sewing](../EXAMPLES.md#3-prepare-a-mannequin-for-sewing), then continue to [Direct fitting and arrangement](03-fitting.md) to position garment pieces on the target.

## How the viewport editor behaves

The labelled lines, markers, and circumference rings are transient viewport overlay geometry. They do not add FreeCAD document objects. A drag updates the staged task-panel value; **Apply & Rebuild** is the commit boundary. Closing the editor removes the overlay and its callbacks. The 3D Pattern Pen remains a separate authoring tool and is not reused by this editor.

If a build cannot initialise the viewport interaction, use the numeric measurement fields. Imported FreeCAD geometry is a surface provider rather than a parametric human body, so its shape and measurement controls are disabled.

## Scope and limitations

The editor currently applies deterministic, localized procedural deformations to the bundled HM08 mannequin. It does not yet load the full MakeHuman target-morph library, and the gender blend is not a high-fidelity commercial avatar morph system. Cup-size-specific garment grading is not inferred from the breast-fullness slider; set bust and underbust circumferences as measurements and treat shape fullness as a separate visual/body-surface control.

When the mesh is rebuilt, fitting anchors are refreshed against the stable avatar mesh where possible. If an anchor is visibly marked stale or no longer follows the intended surface, recreate it before arranging fabric. Always review the actual garment-to-target relationship before running simulation.

## Evidence and implementation

The editor screenshot and interaction GIFs are generated by the FreeCAD GUI acceptance fixture. The profile gallery is a programmatic composition of same-scale FreeCAD viewport captures of the actual HM08 mesh, not a hand-authored avatar illustration.

- Acceptance and GIF source: <code>tests/freecad_avatar_shape_editor_acceptance.py</code>
- Model/persistence: <code>freecad_cloth/avatar/AvatarModel.py</code> and <code>freecad_cloth/avatar/AvatarCommands.py</code>
- Mesh deformation: <code>freecad_cloth/avatar/HumanoidMesh.py</code>
- Task panel: <code>freecad_cloth/avatar/AvatarGui.py</code>
- Transient dimension handles: <code>freecad_cloth/avatar/AvatarShapeGui.py</code>

Continue with [Pose Mode](04-pose.md) when the mannequin's body proportions are correct but its posture needs adjustment.

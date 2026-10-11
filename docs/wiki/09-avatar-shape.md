# 09 · Avatar shape and dimensions

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-shape-editor.png" alt="Edit Avatar task panel showing body-shape controls, numeric measurements, and transient 3D dimension handles around the mannequin" width="900"></p>

Use this editor to prepare a mannequin for pattern fitting and sewing. It separates broad body-shape controls from named, millimetre-based measurements, and keeps the viewport as the primary place to discover and adjust dimensions.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-shape-edit.gif" alt="Changing the feminine-to-masculine body-shape blend and breast fullness, then applying and rebuilding the mannequin" width="900"></p>

**What this clip shows:** the shape sliders are staged, then **Apply & Rebuild** updates the bare mannequin mesh. It is **not a cloth simulation**: there is no garment in this clip and no drape solver is running. See the [simulation guide](05-simulation.md) for cloth behavior.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-dimension-drag.gif" alt="Dragging the mannequin hip circumference handle to stage a local measurement, then applying and rebuilding the body" width="900"></p>

## Compare example body shapes

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-body-shape-gallery.png" alt="Seven real FreeCAD HM08 mannequin renders showing feminine, masculine, slim, plus-size, muscular, tall, and petite example body shapes at a shared orthographic scale" width="1000"></p>

The gallery is rendered from the pinned HM08 mannequin mesh using the existing **Gender blend**, **Breast fullness**, and measurement inputs. The mesh is reused from a matching local MakeHuman installation when found, or downloaded from the pinned upstream revision and cached on first use. Camera scale stays fixed across all seven views, so body height and breadth remain comparable. Each card shows its height, waist, hip, and shape-control values.

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


### Base mesh lookup and offline behavior

The HM08 base mesh is not bundled in the workbench package. The loader first uses its checksum-verified cache, then checks common MakeHuman installation paths and the optional `FREECAD_CLOTH_MAKEHUMAN_DATA` setting, and finally downloads the pinned mesh into the cache. Set that variable to a MakeHuman installation root or data directory to prioritize a particular local installation. Auto-discovery accepts only a byte-for-byte match for the pinned mesh so its vertex indices remain compatible with the authored rig data. `FREECAD_CLOTH_AVATAR_MESH` remains an explicit path override and may point to a custom OBJ.

The default skinning weights and skeleton are managed as separate cached downloads, with their own `FREECAD_CLOTH_AVATAR_WEIGHTS` and `FREECAD_CLOTH_AVATAR_SKELETON` overrides. Finding the base mesh locally therefore does not by itself guarantee fully offline setup; the required weights and skeleton must also already be cached or configured locally.

## Shape deformation model and limitations

The HM08 shape fitter uses separate lateral and depth profiles for circumference changes instead of scaling each torso cross-section equally in both directions. Waist, hip, underbust, and chest changes are constrained by a stable soft torso envelope, while shoulder breadth and the gender blend use a separate shoulder-girdle envelope that tapers into the upper arms. This prevents a torso control from moving distal arm/hand vertices merely because they happen to share the same height in a pose.

The skeleton and pose overlay also derive joint centers by fitting the authored joint vertices individually before averaging them. This is important because the body-shape mapping is nonlinear: mapping the average source point can place a joint somewhere different from the center of the fitted joint surface.

The fitter now supports MakeHuman HM08 sparse morph targets when a compatible MakeHuman or MPFB2 target library is installed. It parses plain, gzip-compressed, and archived targets, preserves vertex indexing, and converts MPFB2's Blender-oriented X/Z/-Y offsets back into the MakeHuman source axes when its target metadata is detected. It blends selected gender/breast-volume and directional measurement targets, and keeps asset files external because they are distributed separately from this workbench. Existing MakeHuman installations, including both loose data trees and the standard `targets.npz` archive, are discovered automatically in common data locations; set `FREECAD_CLOTH_MAKEHUMAN_TARGETS` to a target directory, a MakeHuman `data` directory, or a checkout of `makehuman-assets` to select another library. If no target library is present, fitting continues with the deterministic procedural shape controls.

For hip, high-hip, waist, underbust, and bust/chest, the fitter also measures the actual closed mesh contour at each named height and iteratively corrects the local width/depth profile toward the requested circumference. The contour correction is topology-based and runs after target deltas are applied, so authored target shape and numeric circumference remain separate controls. Other circumference dimensions use the available MakeHuman targets when installed, but are not yet independently guaranteed to match an exact mesh-intersection perimeter. Cup-size-specific garment grading is not inferred from the breast-fullness slider; set bust and underbust circumferences as measurements and treat shape fullness as a separate surface-shape control.

When the mesh is rebuilt, fitting anchors are refreshed against the stable avatar mesh where possible. If an anchor is visibly marked stale or no longer follows the intended surface, recreate it before arranging fabric. Always review the actual garment-to-target relationship before running simulation.

## Evidence and implementation

The editor screenshot and interaction GIFs are generated by the FreeCAD GUI acceptance fixture. The profile gallery is a programmatic composition of same-scale FreeCAD viewport captures of the actual HM08 mesh, not a hand-authored avatar illustration.

- Editor screenshot and interaction GIF source: <code>tests/freecad_avatar_shape_editor_acceptance.py</code>
- Profile gallery renders and composition: <code>tests/freecad_avatar_screenshot.py</code>
- Model/persistence: <code>freecad_cloth/avatar/AvatarModel.py</code> and <code>freecad_cloth/avatar/AvatarCommands.py</code>
- Mesh deformation and contour fitting: <code>freecad_cloth/avatar/HumanoidMesh.py</code>
- MakeHuman sparse morph-target loading: <code>freecad_cloth/avatar/MakeHumanTargets.py</code>
- Task panel: <code>freecad_cloth/avatar/AvatarGui.py</code>
- Transient dimension handles: <code>freecad_cloth/avatar/AvatarShapeGui.py</code>

Continue with [Pose Mode](04-pose.md) when the mannequin's body proportions are correct but its posture needs adjustment.

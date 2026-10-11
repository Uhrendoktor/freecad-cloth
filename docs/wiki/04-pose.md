# 04 · Mannequin Pose Mode

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-pose-mode.png" alt="Pose Mode task panel with visible mannequin joints and a selected shoulder rotation gizmo" width="900"></p>

The image above is the dedicated Pose Mode interaction fixture. It is captured from the active FreeCAD window after the viewport is fitted and painted, with the left shoulder selected so the native three-axis Coin3D rotation gizmo with cone tips and spherical pivot is visible.

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-front.png" alt="Mannequin front view" width="280"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-rear.png" alt="Mannequin rear view" width="280"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-left.png" alt="Mannequin left view" width="200"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-right.png" alt="Mannequin right view" width="200"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-top.png" alt="Mannequin top view" width="200"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-bottom.png" alt="Mannequin bottom view" width="200"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-turntable.gif" alt="Mannequin 360 degree turntable" width="820"></p>

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/pose-joint-rotation.gif" alt="Selecting an upper-arm joint and editing its exact rotation angle in Pose Mode" width="900"></p>

This recording shows joint selection and a keyboard-edited Exact angles value in the live Pose Mode panel. This path works in headless CI builds where native Pivy viewport callbacks cannot be registered safely.

## Pose the mannequin

Pose Mode is optional when a generic FreeCAD shape is the target or the default mannequin position is suitable. The short recording illustrates a joint edit; the complete text path is:

1. Select the mannequin and open **Pose Mode**.
2. Choose a starting pose preset when useful.
3. Select the anatomical joint in the viewport and drag its rotation gizmo. Use **Mirror** and **5° Snap** only when those behaviors are intended.
4. Expand **Joint list** or **Exact angles** if the view is crowded or the rotation needs a precise numeric value.
5. Apply and rebuild the staged pose. Use Cancel to discard staged edits; then confirm the pose and its target-dependent geometry before simulating.

**Verify the result:** the selected joint is unambiguous, parent rotations affect descendants, and the saved pose survives a document round trip. For geometry review, use the multi-side audit images separately from the Pose Mode interaction capture.


## What the feature is

Pose Mode is a dedicated human-facing editor for the mannequin skeleton and pose.

The viewport is the primary manipulation surface. The task panel keeps only direct-pose aids visible: starting-pose buttons, Mirror/5° Snap toggles, the selected-joint readout, and recovery/commit actions. The joint list and exact angle entry are secondary fallbacks.

The current implementation is manual forward kinematics. Parent joint rotations propagate to descendants through the authored skeleton hierarchy.

The native interaction path uses three FreeCAD Coin3D SoRotationDraggers, one per axis, with a near-complete colored ring, cone arrowheads and spherical pivot geometry. The selected bone is kept in a depth-independent overlay so the full X-ray rig remains visible. FreeCAD builds without the native rotation dragger use SoTrackballDragger as an interactive compatibility fallback; builds without the Coin/SWIG bridge retain the joint list and exact angle entry as non-viewport fallback controls.

## What a human should see

| Control | Visual proof to look for |
| --- | --- |
| Joint selection | A selected anatomical joint is obvious in the viewport/tree |
| Rotation gizmo | Three color-coded rotation rings with cone tips and a spherical pivot afford direct manipulation |
| Symmetry | Left/right edits can be mirrored across the sagittal plane |
| 5° snap | Rotation feedback visibly changes in quantized increments |
| Presets | Standing, Sewing and Sitting provide recognizable starting poses |
| Precision | Exact X/Y/Z rotation controls are available without cluttering the default view |
| Apply & Rebuild | A staged pose can be committed explicitly |
| Cancel | Staged edits can be discarded without replacing the saved pose |

## Visual evidence versus geometry review

The front/rear/side/top/bottom images below are geometry-only mannequin audit renders. They are intentionally generated by `tests/freecad_avatar_screenshot.py` without opening Pose Mode, so they are not evidence of joint selection, gizmo interaction or screen-space controls.

The Pose Mode screenshot above is the evidence for the interactive rig. The six-side renders are evidence that the derived mannequin geometry remains sane from multiple viewpoints.

## Persistence model

The pose is document data. Joint rotations are persistent; deformed mannequin geometry is derived and rebuildable.

The implementation intentionally does not turn Pose Mode into a general IK, retargeting or motion-capture system.

The persisted pose also feeds fitting state. Changing the authored pose changes target-dependent derived geometry and should invalidate or rebuild affected collision state deterministically.

## Symmetry

Bilateral symmetry is a real transform, not a screen-space copy.

For the current sagittal mirror convention, the bilateral mapping preserves the rotation component around the mirror-normal axis while negating the two tangential components. The practical audit criterion is simpler: a symmetric left/right edit must produce a geometrically mirrored pose, not the same signed Euler triplet on both sides.

## Human failure review

Treat these as failures:

- a joint moves visually but the saved pose does not change;
- Apply updates the viewport but not persistent state;
- Cancel still changes the mannequin after the staged edit;
- mirrored joints rotate in the same physical direction instead of mirrored directions;
- a parent joint fails to move its descendants;
- target geometry is updated using a stale pre-pose collision surface.

## Automated evidence

Primary fixtures:

- <code>tests/freecad_avatar_pose_ui_acceptance.py</code>
- <code>tests/freecad_avatar_acceptance.py</code>
- <code>tests/freecad_avatar_screenshot.py</code>

Source:

- <code>freecad_cloth/avatar/AvatarPoseGui.py</code>
- <code>freecad_cloth/avatar/SkeletonPose.py</code>
- <code>freecad_cloth/avatar/HierarchicalPose.py</code>
- <code>freecad_cloth/avatar/HumanoidMesh.py</code>
- <code>freecad_cloth/avatar/AvatarModel.py</code>

The avatar screenshot generator is also the source for the six-side mannequin review and avatar turntable.

## Visual design rationale

The rotation control follows established 3D-manipulation conventions: three color-coded axis rings provide the primary affordance, small cone tips clarify the direction of each arc, and spherical pivots mark the selected joint. The implementation reuses FreeCAD's native rotation-dragger geometry rather than drawing a separate imitation control.

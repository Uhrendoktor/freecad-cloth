# 04 · Mannequin Pose Mode

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/avatar-pose-mode.png" alt="Pose Mode with mannequin joints, controls and rotation gizmo" width="900"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-front.png" alt="Mannequin front view" width="280"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-rear.png" alt="Mannequin rear view" width="280"></p>

## What the feature is

Pose Mode is a dedicated human-facing editor for the mannequin skeleton and pose.

The viewport is the primary manipulation surface. The task panel provides selection, symmetry, angle snapping, presets, exact rotation fields and explicit Apply/Cancel behavior.

The current implementation is manual forward kinematics. Parent joint rotations propagate to descendants through the authored skeleton hierarchy.

## What a human should see

| Control | Visual proof to look for |
| --- | --- |
| Joint selection | A selected anatomical joint is obvious in the viewport/tree |
| Rotation gizmo | Axis rings or trackball afford direct manipulation |
| Symmetry | Left/right edits can be mirrored across the sagittal plane |
| 5° snap | Rotation feedback visibly changes in quantized increments |
| Presets | Standing, Sewing and Sitting provide recognizable starting poses |
| Precision | Exact X/Y/Z rotation controls are available without cluttering the default view |
| Apply & Rebuild | A staged pose can be committed explicitly |
| Cancel | Staged edits can be discarded without replacing the saved pose |

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

"""Shared visual tokens for transient Cloth viewport gizmos.

The palette is semantic rather than a full application theme: axis values retain
the familiar XYZ convention; amber is an active control, cyan a live snap target,
and amber active controls, cyan live snap targets. Seam identity colors stay in seam_colors.
"""

# Standard world-axis convention (RGB) used by the rotation gizmo.
POSE_AXIS_COLORS = {
    "X": (0.86, 0.18, 0.16),
    "Y": (0.18, 0.70, 0.26),
    "Z": (0.18, 0.40, 0.88),
}

# Active/selected controls should be readable without overwhelming the model.
ACTIVE_COLOR = (1.0, 0.78, 0.20)
RIG_PASSIVE_COLOR = (0.46, 0.48, 0.52)
RIG_EDITABLE_COLOR = (0.72, 0.75, 0.80)
JOINT_COLOR = (0.66, 0.68, 0.72)

# Task-specific cue: cyan for live snap feedback.
SNAP_TARGET_COLOR = (0.15, 0.75, 1.0)

# Pose rig emphasis levels.
RIG_PASSIVE_LINE_WIDTH = 1.4
RIG_EDITABLE_LINE_WIDTH = 2.4
RIG_ACTIVE_LINE_WIDTH = 4.0
RIG_JOINT_POINT_SIZE = 7.0
RIG_ACTIVE_JOINT_POINT_SIZE = 14.0

# Native axis rotation dragger geometry (model-space dimensions).
ROTATION_GIZMO_SCALE = 7.0
ROTATION_ARC_ANGLE_DEGREES = 300.0
ROTATION_RING_RADIUS = 9.5
ROTATION_RING_THICKNESS = 2.8
ROTATION_PIVOT_RADIUS = 0.9
ROTATION_ARROW_RADIUS = 1.35
ROTATION_ARROW_HEIGHT = 3.8

# Arrangement snap markers are intentionally simple and spatially legible.
SNAP_LINE_WIDTH = 2.0
SNAP_RING_RADIUS = 8.0
SNAP_RING_SEGMENTS = 48
SNAP_CENTER_RADIUS = 0.8
SNAP_CROSSHAIR_HALF_LENGTH = 11.0


# Seam lines remain identity-colored; these weights control visual hierarchy only.
SEAM_LINE_WIDTH = 2.4
SEAM_FOCUSED_LINE_WIDTH = 4.0
SEAM_CONNECTOR_LINE_WIDTH = 1.25
SEAM_LABEL_FONT_SIZE = 16.0

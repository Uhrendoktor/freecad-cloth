# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared visual tokens for transient Cloth viewport gizmos.

The palette is semantic rather than a full application theme. Axis colors retain
the familiar XYZ convention; amber denotes active controls and cyan denotes live snap
targets. Semantic seam identity colors remain owned by seam_colors.
"""

# Standard world-axis convention (RGB) used by the rotation gizmo.
POSE_AXIS_COLORS = {
    "X": (0.86, 0.18, 0.16),
    "Y": (0.18, 0.70, 0.26),
    "Z": (0.18, 0.40, 0.88),
}

# Active/selected controls should be readable without overwhelming the model.
ACTIVE_COLOR = (1.0, 0.78, 0.20)
RIG_PASSIVE_COLOR = (0.61, 0.65, 0.72)
RIG_EDITABLE_COLOR = (0.84, 0.88, 0.95)
JOINT_COLOR = (0.77, 0.81, 0.89)
DIMENSION_GUIDE_COLOR = (0.25, 0.68, 0.79)
DIMENSION_GUIDE_LINE_WIDTH = 1.8

# Task-specific cue: cyan for live snap feedback.
SNAP_TARGET_COLOR = (0.15, 0.75, 1.0)
SNAP_STALE_COLOR = (0.95, 0.24, 0.16)

# Pose rig radii are screen-space pixels converted locally through the active camera.
RIG_PASSIVE_RADIUS = 1.7
RIG_EDITABLE_RADIUS = 2.4
RIG_ACTIVE_RADIUS = 3.8
RIG_JOINT_RADIUS = 2.8
RIG_ACTIVE_JOINT_RADIUS = 4.5

# Native axis rotation dragger geometry (model-space dimensions).
ROTATION_GIZMO_SCALE = 8.5
ROTATION_ARC_ANGLE_DEGREES = 300.0
ROTATION_RING_RADIUS = 10.5
ROTATION_RING_THICKNESS = 3.2
ROTATION_PIVOT_RADIUS = 0.9
ROTATION_ARROW_RADIUS = 1.5
ROTATION_ARROW_HEIGHT = 4.2
# Camera-facing outer ring provides a screen-space roll control around the view axis.
ROTATION_VIEW_COLOR = (0.82, 0.85, 0.90)
ROTATION_VIEW_RING_RADIUS = 14.5
ROTATION_VIEW_RING_THICKNESS = 2.2

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


# Measurement guides use a higher-contrast X-ray underlay behind the mannequin.
# Foreground grips are nested 3D spheres; radii and increments are screen-space pixels.
DIMENSION_OCCLUDED_COLOR = (0.48, 0.65, 0.72)
DIMENSION_OCCLUDED_LINE_WIDTH = 1.6
DIMENSION_OCCLUDED_LINE_PATTERN = 0x0F0F
DIMENSION_OCCLUDED_LINE_PATTERN_SCALE = 2
DIMENSION_MARKER_HALO_COLOR = (0.96, 0.97, 0.98)
DIMENSION_MARKER_OUTLINE_COLOR = (0.08, 0.10, 0.12)
DIMENSION_MARKER_HALO_RADIUS_INCREMENT = 6.0
DIMENSION_MARKER_OUTLINE_RADIUS_INCREMENT = 3.0

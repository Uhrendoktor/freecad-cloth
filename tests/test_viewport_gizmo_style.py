# Copyright (C) 2026 FreeCAD Cloth contributors
"""Design-contract tests for shared viewport gizmo presentation."""

import ast
from pathlib import Path

from freecad_cloth.shared.ViewportGizmoStyle import (
    ACTIVE_COLOR,
    DIMENSION_GUIDE_COLOR,
    DIMENSION_GUIDE_LINE_WIDTH,
    DIMENSION_MARKER_HALO_COLOR,
    DIMENSION_MARKER_HALO_RADIUS_INCREMENT,
    DIMENSION_MARKER_OUTLINE_COLOR,
    DIMENSION_MARKER_OUTLINE_RADIUS_INCREMENT,
    DIMENSION_OCCLUDED_COLOR,
    DIMENSION_OCCLUDED_LINE_PATTERN,
    DIMENSION_OCCLUDED_LINE_PATTERN_SCALE,
    DIMENSION_OCCLUDED_LINE_WIDTH,
    JOINT_COLOR,
    POSE_AXIS_COLORS,
    RIG_ACTIVE_JOINT_RADIUS,
    RIG_ACTIVE_RADIUS,
    RIG_EDITABLE_RADIUS,
    RIG_JOINT_RADIUS,
    RIG_OUTLINE_COLOR,
    RIG_OUTLINE_RADIUS_SCALE,
    RIG_PASSIVE_RADIUS,
    ROTATION_GIZMO_SCALE,
    ROTATION_RING_RADIUS,
    ROTATION_VIEW_COLOR,
    ROTATION_VIEW_RING_RADIUS,
    ROTATION_VIEW_RING_THICKNESS,
    SEAM_CONNECTOR_LINE_WIDTH,
    SEAM_FOCUSED_LINE_WIDTH,
    SEAM_LABEL_FONT_SIZE,
    SEAM_LINE_WIDTH,
    SNAP_CENTER_RADIUS,
    SNAP_CROSSHAIR_HALF_LENGTH,
    SNAP_LINE_WIDTH,
    SNAP_RING_RADIUS,
    SNAP_RING_SEGMENTS,
    SNAP_STALE_COLOR,
    SNAP_TARGET_COLOR,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AXIS_ORDER = ("X", "Y", "Z")
EXPECTED_AXIS_COLOR_COUNT = 3
EXPECTED_RGB_COMPONENT_COUNT = 3
MINIMUM_RGB_COMPONENT = 0.0
MAXIMUM_RGB_COMPONENT = 1.0
MINIMUM_POSITIVE_STYLE_VALUE = 0.0
MINIMUM_SNAP_RING_SEGMENTS = 32


def _assert_rgb(rgb: tuple[float, float, float]) -> None:
    """Check that a semantic color is a normalized RGB triple.

    Args:
        rgb: Three normalized channel values representing red, green, and blue.
    """
    assert len(rgb) == EXPECTED_RGB_COMPONENT_COUNT, (
        "Semantic colors must contain exactly three RGB channels."
    )
    assert all(
        MINIMUM_RGB_COMPONENT <= float(channel) <= MAXIMUM_RGB_COMPONENT for channel in rgb
    ), "RGB channel values must remain within the normalized range."


def test_pose_axis_colors_keep_the_standard_xyz_identity() -> None:
    """Keep axis identity stable for spatial recognition."""
    assert tuple(POSE_AXIS_COLORS) == EXPECTED_AXIS_ORDER, (
        "Pose gizmo axes must retain the standard XYZ ordering."
    )
    x, y, z = (POSE_AXIS_COLORS[axis] for axis in EXPECTED_AXIS_ORDER)
    assert x[0] > x[1], "X-axis color should emphasize red."
    assert x[0] > x[2], "X-axis color should emphasize red."
    assert y[1] > y[0], "Y-axis color should emphasize green."
    assert y[1] > y[2], "Y-axis color should emphasize green."
    assert z[2] > z[0], "Z-axis color should emphasize blue."
    assert z[2] > z[1], "Z-axis color should emphasize blue."
    assert len({x, y, z}) == EXPECTED_AXIS_COLOR_COUNT, (
        "Each spatial axis must have a distinct color."
    )


def test_gizmo_semantic_colors_are_valid_and_distinct() -> None:
    """Keep active, snap and axis cues independently identifiable."""
    colors = (
        *POSE_AXIS_COLORS.values(),
        ACTIVE_COLOR,
        DIMENSION_GUIDE_COLOR,
        DIMENSION_OCCLUDED_COLOR,
        DIMENSION_MARKER_HALO_COLOR,
        DIMENSION_MARKER_OUTLINE_COLOR,
        ROTATION_VIEW_COLOR,
        JOINT_COLOR,
        RIG_OUTLINE_COLOR,
        SNAP_TARGET_COLOR,
        SNAP_STALE_COLOR,
    )
    for rgb in colors:
        _assert_rgb(rgb)
    assert len(set(colors)) == len(colors), "All semantic gizmo colors must be distinct."
    assert ACTIVE_COLOR not in POSE_AXIS_COLORS.values(), (
        "The active-selection color must differ from every axis color."
    )


def test_gizmo_dimensions_keep_clear_visual_hierarchy() -> None:
    """Guard line and marker hierarchy without pinning rendering to exact pixels."""
    assert (
        MINIMUM_POSITIVE_STYLE_VALUE < RIG_PASSIVE_RADIUS < RIG_EDITABLE_RADIUS < RIG_ACTIVE_RADIUS
    ), "Passive, editable, and active capsule radii must increase in emphasis."
    assert MINIMUM_POSITIVE_STYLE_VALUE < RIG_JOINT_RADIUS < RIG_ACTIVE_JOINT_RADIUS, (
        "Active spherical joints must be larger than ordinary joints."
    )
    assert RIG_PASSIVE_RADIUS >= 3.0, (
        "Passive bone shafts must retain a visible inner core inside the outline."
    )
    assert RIG_EDITABLE_RADIUS >= 4.0, "Editable bone shafts must have a readable viewport width."
    assert RIG_ACTIVE_RADIUS >= 6.0, (
        "The active bone must remain distinguishable over the mannequin."
    )
    assert RIG_JOINT_RADIUS >= 4.0, "Spherical joints must remain visible at fitted avatar scale."
    assert RIG_OUTLINE_RADIUS_SCALE >= 1.5, (
        "Bone/joint outlines must be wider than their semantic center geometry."
    )
    _assert_rgb(RIG_OUTLINE_COLOR)
    assert (
        MINIMUM_POSITIVE_STYLE_VALUE
        < DIMENSION_MARKER_OUTLINE_RADIUS_INCREMENT
        < DIMENSION_MARKER_HALO_RADIUS_INCREMENT
    ), "The spherical measurement grip must have nested rim and halo radii."
    assert ROTATION_GIZMO_SCALE > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Rotation gizmo scale must be positive."
    )
    assert ROTATION_RING_RADIUS > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Rotation ring radius must be positive."
    )
    assert ROTATION_VIEW_RING_RADIUS > ROTATION_RING_RADIUS, (
        "The camera-facing ring must sit outside the anatomical axis rings."
    )
    assert ROTATION_VIEW_RING_THICKNESS > MINIMUM_POSITIVE_STYLE_VALUE
    _assert_rgb(ROTATION_VIEW_COLOR)
    assert DIMENSION_GUIDE_LINE_WIDTH > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Dimension guide line width must be positive."
    )
    assert DIMENSION_OCCLUDED_LINE_WIDTH > MINIMUM_POSITIVE_STYLE_VALUE
    assert DIMENSION_OCCLUDED_LINE_WIDTH < DIMENSION_GUIDE_LINE_WIDTH
    assert 0 < DIMENSION_OCCLUDED_LINE_PATTERN < 0xFFFF
    assert DIMENSION_OCCLUDED_LINE_PATTERN_SCALE >= 1
    _assert_rgb(DIMENSION_OCCLUDED_COLOR)
    _assert_rgb(DIMENSION_MARKER_HALO_COLOR)
    _assert_rgb(DIMENSION_MARKER_OUTLINE_COLOR)
    assert SNAP_LINE_WIDTH > MINIMUM_POSITIVE_STYLE_VALUE, "Snap line width must be positive."
    assert SNAP_RING_RADIUS > SNAP_CENTER_RADIUS > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Snap ring must surround its center marker."
    )
    assert SNAP_CROSSHAIR_HALF_LENGTH > SNAP_RING_RADIUS, (
        "Snap crosshair must extend past the ring radius."
    )
    assert SNAP_RING_SEGMENTS >= MINIMUM_SNAP_RING_SEGMENTS, (
        "Snap ring must use enough segments to appear smooth."
    )
    assert MINIMUM_POSITIVE_STYLE_VALUE < SEAM_LINE_WIDTH < SEAM_FOCUSED_LINE_WIDTH, (
        "Focused seams must be emphasized over ordinary seam lines."
    )
    assert MINIMUM_POSITIVE_STYLE_VALUE < SEAM_CONNECTOR_LINE_WIDTH < SEAM_LINE_WIDTH, (
        "Seam connectors must remain visually subordinate to seam lines."
    )
    assert SEAM_LABEL_FONT_SIZE > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Seam label font size must be positive."
    )


def test_each_shared_style_overlay_uses_visual_tokens() -> None:
    """Catch a viewport overlay reintroducing local palette and weight literals."""
    requirements = {
        "freecad_cloth/avatar/AvatarPoseGui.py": {
            "ACTIVE_COLOR",
            "POSE_AXIS_COLORS",
            "RIG_PASSIVE_COLOR",
            "RIG_EDITABLE_COLOR",
            "RIG_OUTLINE_COLOR",
            "RIG_OUTLINE_RADIUS_SCALE",
            "RIG_PASSIVE_RADIUS",
            "RIG_EDITABLE_RADIUS",
            "RIG_ACTIVE_RADIUS",
            "RIG_JOINT_RADIUS",
            "RIG_ACTIVE_JOINT_RADIUS",
            "ROTATION_GIZMO_SCALE",
            "ROTATION_VIEW_COLOR",
            "ROTATION_VIEW_RING_RADIUS",
            "ROTATION_VIEW_RING_THICKNESS",
        },
        "freecad_cloth/avatar/AvatarShapeGui.py": {
            "DIMENSION_GUIDE_COLOR",
            "DIMENSION_GUIDE_LINE_WIDTH",
            "DIMENSION_OCCLUDED_COLOR",
            "DIMENSION_OCCLUDED_LINE_PATTERN",
            "DIMENSION_OCCLUDED_LINE_PATTERN_SCALE",
            "DIMENSION_OCCLUDED_LINE_WIDTH",
            "DIMENSION_MARKER_HALO_COLOR",
            "DIMENSION_MARKER_HALO_RADIUS_INCREMENT",
            "DIMENSION_MARKER_OUTLINE_COLOR",
            "DIMENSION_MARKER_OUTLINE_RADIUS_INCREMENT",
        },
        "freecad_cloth/avatar/FittingGui.py": {
            "SNAP_TARGET_COLOR",
            "SNAP_STALE_COLOR",
            "SNAP_RING_RADIUS",
            "SNAP_RING_SEGMENTS",
            "SNAP_CROSSHAIR_HALF_LENGTH",
        },
        "freecad_cloth/sewing/SeamOverlay.py": {
            "SEAM_LINE_WIDTH",
            "SEAM_FOCUSED_LINE_WIDTH",
            "SEAM_CONNECTOR_LINE_WIDTH",
            "SEAM_LABEL_FONT_SIZE",
        },
    }
    for relative_path, names in requirements.items():
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        imports = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "freecad_cloth.shared.ViewportGizmoStyle"
            for alias in node.names
        }
        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        assert names <= imports, f"{relative_path}: missing one or more shared style imports."
        assert names <= loaded_names, (
            f"{relative_path}: required style tokens are imported but unused."
        )

    for relative_path in (
        "freecad_cloth/avatar/AvatarPoseGui.py",
        "freecad_cloth/avatar/AvatarShapeGui.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "SoPointSet" not in source, (
            f"{relative_path}: avatar bone and measurement controls must not use square point sprites."
        )
        assert "ViewportGizmoGeometry" in source, (
            f"{relative_path}: rounded avatar controls must use the shared Coin3D geometry helpers."
        )

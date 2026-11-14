# Copyright (C) 2026 FreeCAD Cloth contributors
"""Design-contract tests for shared viewport gizmo presentation."""

import ast
from pathlib import Path

from freecad_cloth.shared.ViewportGizmoStyle import (
    ACTIVE_COLOR,
    JOINT_COLOR,
    POSE_AXIS_COLORS,
    RIG_ACTIVE_JOINT_POINT_SIZE,
    RIG_ACTIVE_LINE_WIDTH,
    RIG_EDITABLE_LINE_WIDTH,
    RIG_JOINT_POINT_SIZE,
    RIG_PASSIVE_LINE_WIDTH,
    ROTATION_GIZMO_SCALE,
    ROTATION_RING_RADIUS,
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
        JOINT_COLOR,
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
        MINIMUM_POSITIVE_STYLE_VALUE
        < RIG_PASSIVE_LINE_WIDTH
        < RIG_EDITABLE_LINE_WIDTH
        < RIG_ACTIVE_LINE_WIDTH
    ), "Passive, editable, and active rig lines must increase in emphasis."
    assert MINIMUM_POSITIVE_STYLE_VALUE < RIG_JOINT_POINT_SIZE < RIG_ACTIVE_JOINT_POINT_SIZE, (
        "Active joint markers must be larger than ordinary joint markers."
    )
    assert ROTATION_GIZMO_SCALE > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Rotation gizmo scale must be positive."
    )
    assert ROTATION_RING_RADIUS > MINIMUM_POSITIVE_STYLE_VALUE, (
        "Rotation ring radius must be positive."
    )
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
            "ROTATION_GIZMO_SCALE",
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

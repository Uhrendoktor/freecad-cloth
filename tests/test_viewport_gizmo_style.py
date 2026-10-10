"""Design-contract tests for shared viewport gizmo presentation."""

import ast
from pathlib import Path

from freecad_cloth.shared.viewport_gizmo_style import (
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
    SNAP_TARGET_COLOR,
)

ROOT = Path(__file__).resolve().parents[1]


def _assert_rgb(rgb: tuple[float, float, float]) -> None:
    """Check that a semantic color is a normalized RGB triple."""
    assert len(rgb) == 3
    assert all(0.0 <= float(channel) <= 1.0 for channel in rgb)


def test_pose_axis_colors_keep_the_standard_xyz_identity() -> None:
    """Keep axis identity stable for spatial recognition."""
    assert tuple(POSE_AXIS_COLORS) == ("X", "Y", "Z")
    x, y, z = (POSE_AXIS_COLORS[axis] for axis in ("X", "Y", "Z"))
    assert x[0] > x[1] and x[0] > x[2]
    assert y[1] > y[0] and y[1] > y[2]
    assert z[2] > z[0] and z[2] > z[1]
    assert len({x, y, z}) == 3


def test_gizmo_semantic_colors_are_valid_and_distinct() -> None:
    """Keep active, snap and axis cues independently identifiable."""
    colors = (
        *POSE_AXIS_COLORS.values(),
        ACTIVE_COLOR,
        JOINT_COLOR,
        SNAP_TARGET_COLOR,
    )
    for rgb in colors:
        _assert_rgb(rgb)
    assert len(set(colors)) == len(colors)
    assert ACTIVE_COLOR not in POSE_AXIS_COLORS.values()


def test_gizmo_dimensions_keep_clear_visual_hierarchy() -> None:
    """Guard line and marker hierarchy without pinning rendering to exact pixels."""
    assert 0.0 < RIG_PASSIVE_LINE_WIDTH < RIG_EDITABLE_LINE_WIDTH < RIG_ACTIVE_LINE_WIDTH
    assert 0.0 < RIG_JOINT_POINT_SIZE < RIG_ACTIVE_JOINT_POINT_SIZE
    assert ROTATION_GIZMO_SCALE > 0.0
    assert ROTATION_RING_RADIUS > 0.0
    assert SNAP_LINE_WIDTH > 0.0
    assert SNAP_RING_RADIUS > SNAP_CENTER_RADIUS > 0.0
    assert SNAP_CROSSHAIR_HALF_LENGTH > SNAP_RING_RADIUS
    assert SNAP_RING_SEGMENTS >= 32
    assert 0.0 < SEAM_LINE_WIDTH < SEAM_FOCUSED_LINE_WIDTH
    assert 0.0 < SEAM_CONNECTOR_LINE_WIDTH < SEAM_LINE_WIDTH
    assert SEAM_LABEL_FONT_SIZE > 0.0


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
            and node.module == "freecad_cloth.shared.viewport_gizmo_style"
            for alias in node.names
        }
        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        assert names <= imports, f"{relative_path}: missing shared style imports"
        assert names <= loaded_names, f"{relative_path}: tokens imported but not used"

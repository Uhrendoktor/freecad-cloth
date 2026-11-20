# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral contract checks for the avatar task-panel boundary.

The expensive visual behavior is covered by FreeCAD acceptance tests. These tests
exercise exported panel configuration and pure helper behavior without reading
the GUI implementation source.
"""

from __future__ import annotations

import math
from dataclasses import fields
from types import SimpleNamespace

from freecad_cloth.avatar import AvatarCommands
from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS, AvatarParameters, Pose
from freecad_cloth.avatar.AvatarProperties import (
    POSE_PROPERTY_MAP,
    PROPERTY_MAP,
    SHAPE_PROPERTY_MAP,
)


def test_avatar_panel_property_mapping_matches_command_authority():
    assert AvatarTaskPanel.PROPERTY_MAP == AvatarCommands.PROPERTY_MAP
    assert set(AvatarTaskPanel.PROPERTY_MAP) == set(AvatarCommands.DEFAULT_MEASUREMENTS)


def test_avatar_panel_groups_cover_all_editable_measurements():
    grouped = tuple(key for key, _label in AvatarTaskPanel.BODY + AvatarTaskPanel.PROPORTIONS)
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == set(AvatarCommands.DEFAULT_MEASUREMENTS)


def test_avatar_panel_shape_fields_match_persistent_command_properties():
    assert AvatarTaskPanel.SHAPE_PROPERTY_MAP == AvatarCommands.SHAPE_PROPERTY_MAP
    assert AvatarTaskPanel.SHAPE_PROPERTY_MAP == {
        "gender": "Gender",
        "breast_size": "BreastSize",
    }
    assert callable(AvatarTaskPanel._shape_changed)
    assert callable(AvatarTaskPanel._toggle_dimension_gizmo)


def test_parent_panel_has_no_duplicate_pose_state():
    """Keep posing in the dedicated editor rather than hidden parent-panel controls."""
    from freecad_cloth.avatar.AvatarPoseGui import AvatarPoseTaskPanel

    assert not hasattr(AvatarTaskPanel, "POSE_FIELDS")
    assert not hasattr(AvatarTaskPanel, "_pose_property")
    assert not hasattr(AvatarTaskPanel, "_rebuild_geometry")
    assert ("t_pose", "T-pose") in AvatarPoseTaskPanel.PRESETS


def test_avatar_panel_provider_choices_match_authoritative_provider_ids():
    assert tuple(key for key, _label in AvatarTaskPanel.PROVIDERS) == AvatarCommands.PROVIDER_IDS
    assert len(AvatarTaskPanel.PROVIDERS) == len(set(AvatarCommands.PROVIDER_IDS))
    provider_labels = dict(AvatarTaskPanel.PROVIDERS)
    geometry_label = provider_labels["freecad-geometry"].lower()
    assert "surface only" in geometry_label
    assert "skeleton" in geometry_label
    assert "animation" in geometry_label


def test_avatar_panel_exposes_the_public_task_panel_protocol():
    assert callable(AvatarTaskPanel)
    for method in (
        "_add_shape_group",
        "_update_shape_labels",
        "_set_shape_controls",
        "_gender_percent_changed",
        "_breast_percent_changed",
        "_gender_profile_changed",
        "_set_measurement_focus",
        "_set_measurement_hover",
        "_focus_measurement",
        "_update_shape_enabled",
        "_staged_parameters",
        "_apply",
        "_open_pose_mode",
        "_update_arrangement_points",
        "_update_landmarks",
    ):
        assert callable(getattr(AvatarTaskPanel, method, None))


def test_avatar_advanced_search_explains_when_no_parameters_match() -> None:
    """Show a visible empty state in both advanced tabs for an unmatched query."""

    class _Visibility:
        def __init__(self) -> None:
            self.visible = True

        def setVisible(self, value: bool) -> None:
            self.visible = bool(value)

    class _SearchRow(_Visibility):
        def property(self, _name: str) -> str:
            return "arm length"

    class _Tabs:
        def __init__(self) -> None:
            self.index = 0

        def currentIndex(self) -> int:
            return self.index

        def setCurrentIndex(self, value: int) -> None:
            self.index = int(value)

    row = _SearchRow()
    group = _Visibility()
    phenotypes_empty = _Visibility()
    morphs_empty = _Visibility()
    panel = SimpleNamespace(
        _advanced_rows=[{"row": row, "group": group, "page": "morphs"}],
        _advanced_groups=[group],
        _advanced_pages={
            "phenotypes": {"empty_label": phenotypes_empty},
            "morphs": {"empty_label": morphs_empty},
        },
        advanced_tabs=_Tabs(),
    )

    AvatarTaskPanel._filter_advanced_parameters(panel, "parameter-does-not-exist")

    assert row.visible is False
    assert group.visible is False
    assert phenotypes_empty.visible is True
    assert morphs_empty.visible is True


def test_viewport_dimension_handle_drag_math_is_scaled_and_clamped():
    from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController

    # Ten pixels represents 100 mm along this projected 100 mm axis.
    self_value = AvatarDimensionController._dragged_value(
        1750.0, (5.0, 0.0), (10.0, 0.0), 1.0, (1200.0, 2300.0)
    )
    assert self_value == 1800.0
    circumference = AvatarDimensionController._dragged_value(
        900.0, (15.0, 0.0), (10.0, 0.0), 2.0 * math.pi, (600.0, 1600.0)
    )
    assert circumference == 1600.0
    assert (
        AvatarDimensionController._dragged_value(
            1750.0, (0.0, -10.0), (0.0, -20.0), 1.0, (1200.0, 2300.0)
        )
        == 1800.0
    )


def test_trunk_dimension_landmarks_are_distinct_on_the_rig_span() -> None:
    """Keep chest, underbust, waist and hip guides separated along the skeleton."""
    from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController

    pelvis = (-12.0, 8.0, 910.0)
    chest = (24.0, -4.0, 1420.0)
    landmarks = AvatarDimensionController._trunk_landmarks(pelvis, chest)
    ordered = (
        landmarks["hip"],
        landmarks["high_hip"],
        landmarks["waist"],
        landmarks["stomach"],
        landmarks["underbust"],
        landmarks["chest"],
    )
    assert ordered[0] == pelvis
    assert ordered[-1] == chest
    distances = tuple(
        math.dist(ordered[index], ordered[index + 1]) for index in range(len(ordered) - 1)
    )
    assert all(distance > 1.0 for distance in distances)
    axis = AvatarDimensionController._unit(
        tuple(chest[index] - pelvis[index] for index in range(3))
    )
    for point, factor in zip(
        ordered,
        (0.0, 0.18, 0.40, 0.60, 0.80, 1.0),
        strict=True,
    ):
        offset = tuple(point[index] - pelvis[index] for index in range(3))
        projected = AvatarDimensionController._dot(offset, axis)
        expected = factor * math.dist(pelvis, chest)
        assert math.isclose(projected, expected, abs_tol=1e-7)


def test_dimension_ring_basis_is_orthogonal_and_value_scaled() -> None:
    """Keep limb and trunk guide rings circular for arbitrary skeleton axes."""
    from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController

    for normal, radial in (
        ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)),
    ):
        center = (15.0, -7.0, 23.0)
        points = AvatarDimensionController._ring_points(
            center,
            normal,
            radial,
            42.5,
            segments=32,
        )
        assert len(points) == 33
        assert points[0] == points[-1]
        axis = AvatarDimensionController._unit(normal)
        for point in points[:-1]:
            offset = tuple(point[index] - center[index] for index in range(3))
            assert math.isclose(math.dist(point, center), 42.5, abs_tol=1e-7)
            assert abs(AvatarDimensionController._dot(offset, axis)) < 1e-7


def test_measurement_display_labels_are_compact_and_model_backed() -> None:
    """Keep two-up measurement rows compact without losing full tooltip names."""
    labels = AvatarTaskPanel.MEASUREMENT_DISPLAY_LABELS
    assert set(labels) == set(DEFAULT_MEASUREMENTS)
    assert all(1 <= len(label) <= 7 for label in labels.values())
    assert {"neck", "shoulder", "sleeve_length", "back_neck_to_waist"} <= set(labels)


def test_viewport_dimension_field_keys_are_canonical() -> None:
    """Keep every viewport-linked field inside the model's canonical measurement set."""
    assert set(DEFAULT_MEASUREMENTS) >= AvatarTaskPanel.VIEWPORT_DIMENSION_KEYS


def test_measurement_properties_are_generated_from_model_measurements() -> None:
    """Ensure every canonical measurement has the corresponding persisted property."""
    expected = {
        name: "_".join(part.capitalize() for part in name.split("_"))
        for name in DEFAULT_MEASUREMENTS
    }
    assert expected == PROPERTY_MAP, (
        "measurement property names must derive from the AvatarParameters keys"
    )


def test_shape_properties_are_generated_from_model_field_metadata() -> None:
    """Ensure shape properties derive from canonical model-field metadata."""
    expected = {
        field.name: "".join(part.capitalize() for part in field.name.split("_"))
        for field in fields(AvatarParameters)
        if field.metadata.get("freecad_property_group") == "shape"
    }
    assert expected == {"gender": "Gender", "breast_size": "BreastSize"}, (
        "shape fields must carry stable FreeCAD grouping metadata on the model."
    )
    assert expected == SHAPE_PROPERTY_MAP, (
        "shape property names must be derived from AvatarParameters field metadata."
    )


def test_pose_properties_cover_all_pose_angle_fields() -> None:
    """Ensure FreeCAD pose properties track every angle field on the Pose model."""
    expected = {
        field.name: "".join(part.capitalize() for part in field.name.split("_"))
        for field in fields(Pose)
        if field.name.endswith("_angle")
    }
    assert expected == POSE_PROPERTY_MAP, (
        "pose property names must derive from the Pose angle fields"
    )


class _CoinField:
    """Small Coin field stub supporting scalar and multi-point assignments."""

    def __init__(self) -> None:
        self.value: float | tuple[tuple[float, float, float], ...] | None = None

    def setValue(self, value: object) -> None:
        self.value = value

    def setValues(
        self,
        _start: int,
        _count: int,
        values: tuple[tuple[float, float, float], ...],
    ) -> None:
        self.value = values


class _CoinNode:
    """Scene-graph node stub retaining child order for render-state assertions."""

    def __init__(self) -> None:
        self.children: list[_CoinNode] = []

    def addChild(self, child: _CoinNode) -> None:
        self.children.append(child)


class _CoinDrawStyle(_CoinNode):
    """Draw-style stub for screen-sized point and stippled line controls."""

    def __init__(self) -> None:
        super().__init__()
        self.pointSize = 0.0
        self.lineWidth = 0.0
        self.linePattern = 0xFFFF
        self.linePatternScaleFactor = 1


class _CoinBaseColor(_CoinNode):
    """Base-colour stub retaining the normalized RGB value."""

    def __init__(self) -> None:
        super().__init__()
        self.rgb: tuple[float, float, float] | None = None


class _CoinCoordinate3(_CoinNode):
    """Coordinate node stub retaining values supplied by the renderer."""

    def __init__(self) -> None:
        super().__init__()
        self.point = _CoinField()


class _CoinDepthBuffer(_CoinNode):
    """Depth-state stub for testing visible and X-ray geometry."""

    def __init__(self) -> None:
        super().__init__()
        self.test = True
        self.write = True


class _CoinTransform(_CoinNode):
    """Transform stub retaining translation and rotation assignments."""

    def __init__(self) -> None:
        super().__init__()
        self.translation = _CoinField()
        self.rotation = _CoinField()


class _CoinSphere(_CoinNode):
    """Sphere primitive stub used by rounded measurement grips."""

    def __init__(self) -> None:
        super().__init__()
        self.radius = _CoinField()


class _CoinPointSet(_CoinNode):
    """Point primitive stub used by foreground dimension markers."""

    def __init__(self) -> None:
        super().__init__()
        self.numPoints = 0


class _CoinLineSet(_CoinNode):
    """Line primitive stub used by measurement guide geometry."""

    def __init__(self) -> None:
        super().__init__()
        self.numVertices = _CoinField()


def _coin_stub() -> SimpleNamespace:
    """Build one reusable Coin API double for marker and line overlay tests."""
    return SimpleNamespace(
        SoSeparator=_CoinNode,
        SoDepthBuffer=_CoinDepthBuffer,
        SoDrawStyle=_CoinDrawStyle,
        SoBaseColor=_CoinBaseColor,
        SoCoordinate3=_CoinCoordinate3,
        SoPointSet=_CoinPointSet,
        SoLineSet=_CoinLineSet,
        SoTransform=_CoinTransform,
        SoSphere=_CoinSphere,
        SbVec3f=lambda *values: tuple(float(value) for value in values),
    )


def test_measurement_marker_uses_three_rounded_foreground_spheres() -> None:
    """Keep a spherical semantic grip legible over light and dark mannequin surfaces."""
    from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController
    from freecad_cloth.shared.ViewportGizmoStyle import (
        DIMENSION_MARKER_HALO_COLOR,
        DIMENSION_MARKER_HALO_RADIUS_INCREMENT,
        DIMENSION_MARKER_OUTLINE_COLOR,
        DIMENSION_MARKER_OUTLINE_RADIUS_INCREMENT,
    )

    coin = _coin_stub()
    controller = AvatarDimensionController.__new__(AvatarDimensionController)
    controller.overlay = coin.SoSeparator()
    controller.foreground_content = None
    controller._add_marker(coin, (0.0, 0.0, 0.0), (0.9, 0.8, 0.2), 8.0)

    assert len(controller.overlay.children) == 3
    radii = [layer.children[2].radius.value for layer in controller.overlay.children]
    colors = [layer.children[1].rgb for layer in controller.overlay.children]
    assert radii == [
        8.0 + DIMENSION_MARKER_HALO_RADIUS_INCREMENT,
        8.0 + DIMENSION_MARKER_OUTLINE_RADIUS_INCREMENT,
        8.0,
    ]
    assert radii[0] > radii[1] > radii[2]
    assert colors == [
        DIMENSION_MARKER_HALO_COLOR,
        DIMENSION_MARKER_OUTLINE_COLOR,
        (0.9, 0.8, 0.2),
    ]
    assert all(len(layer.children) == 3 for layer in controller.overlay.children)


def test_measurement_guides_can_use_dashed_occluded_xray_underlay() -> None:
    """Configure Coin line stippling independently from the solid depth-tested pass."""
    from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController
    from freecad_cloth.shared.ViewportGizmoStyle import (
        DIMENSION_OCCLUDED_LINE_PATTERN,
        DIMENSION_OCCLUDED_LINE_PATTERN_SCALE,
    )

    coin = _coin_stub()
    controller = AvatarDimensionController.__new__(AvatarDimensionController)
    controller.overlay = coin.SoSeparator()
    controller.guide_overlay = None
    controller._add_line(
        coin,
        ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        (0.3, 0.5, 0.6),
        depth_test=False,
        line_pattern=DIMENSION_OCCLUDED_LINE_PATTERN,
        line_pattern_scale_factor=DIMENSION_OCCLUDED_LINE_PATTERN_SCALE,
    )

    separator = controller.overlay.children[0]
    assert separator.children[0].test is False
    assert separator.children[1].linePattern == DIMENSION_OCCLUDED_LINE_PATTERN
    assert separator.children[1].linePatternScaleFactor == DIMENSION_OCCLUDED_LINE_PATTERN_SCALE

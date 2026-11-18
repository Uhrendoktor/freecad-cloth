# Copyright (C) 2026 FreeCAD Cloth contributors
"""Transient, rig-aligned measurement controls for the staged mannequin editor.

Measurement handles follow the current mannequin skeleton and reuse the task
panel's canonical numeric fields. Surface guide rings depth-test against the
avatar mesh; their compact pick markers remain accessible in the foreground.
The overlay is transient Coin3D UI and never creates document objects.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Sequence
from types import ModuleType
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict

if TYPE_CHECKING:
    from freecad_cloth.avatar.avatar_protocols import AvatarParametersProtocol


_Vector3 = tuple[float, float, float]
_Segment = tuple[_Vector3, _Vector3]
_ScreenPoint = tuple[float, float]


class _MeasurementBoxProtocol(Protocol):
    """Numeric field methods used by viewport measurement handles."""

    def value(self) -> float:
        """Return the current staged numeric value."""
        ...

    def setValue(self, value: float) -> None:
        """Set a staged numeric value."""
        ...


class _AvatarFeatureProtocol(Protocol):
    """Minimal identity surface exposed by the FreeCAD avatar feature."""

    AvatarType: str


class _AvatarPanelProtocol(Protocol):
    """Minimum avatar task-panel surface used by dimension gizmos."""

    App: ModuleType
    Gui: ModuleType
    avatar: _AvatarFeatureProtocol | None
    _boxes: dict[str, _MeasurementBoxProtocol]

    def _provider_id(self) -> str:
        """Return the active avatar provider identifier."""
        ...

    def _staged_parameters(self) -> AvatarParametersProtocol:
        """Return the current validated staged avatar parameters."""
        ...

    def _set_measurement_hover(self, key: str | None) -> None:
        """Highlight one measurement field during viewport hover."""
        ...

    def _focus_measurement(self, key: str) -> None:
        """Focus the numeric field linked to a clicked viewport handle."""
        ...

    def _set_status(self, message: str, *, state: str = "info") -> None:
        """Show a staged interaction status."""
        ...


class _CoinMouseEventProtocol(Protocol):
    """Mouse event surface exposed by Coin callback wrappers."""

    def getPosition(self) -> tuple[int, int]:
        """Return the viewport pointer position."""
        ...

    def getState(self) -> int:
        """Return the mouse-button transition state."""
        ...

    def getButton(self) -> int:
        """Return the button that generated the event."""
        ...


class _CoinEventCallbackProtocol(Protocol):
    """Coin callback wrapper operations used by the dimension controller."""

    def getEvent(self) -> _CoinMouseEventProtocol:
        """Return the active Coin mouse event."""
        ...

    def setHandled(self) -> None:
        """Mark a mouse event as handled by the dimension controller."""
        ...


class _RingDimensionSpec(TypedDict):
    """Dimension marker and circle geometry for a circumference field."""

    key: str
    label: str
    shape: Literal["ring"]
    center: _Vector3
    normal: _Vector3
    radial: _Vector3
    radius: float
    point: _Vector3
    axis: _Vector3
    multiplier: float
    bounds: tuple[float, float]


class _LineDimensionSpec(TypedDict):
    """Dimension marker and line geometry for a linear field."""

    key: str
    label: str
    shape: Literal["line"]
    line: _Segment
    point: _Vector3
    axis: _Vector3
    multiplier: float
    bounds: tuple[float, float]


_DimensionSpec = _RingDimensionSpec | _LineDimensionSpec


class AvatarDimensionController:
    """Show and drag staged anthropometric measurements in the FreeCAD viewport."""

    HIT_RADIUS = 28.0
    RING_SEGMENTS = 64
    DRAG_AXIS_LENGTH = 100.0

    def __init__(self, panel: _AvatarPanelProtocol) -> None:
        """Create the dimension overlay state for the supplied avatar task panel.

        Args:
            panel: Avatar task panel that owns the staged measurements and numeric fields.
        """
        self.panel = panel
        self.App = panel.App
        self.Gui = panel.Gui
        self.view = None
        self.scene_graph = None
        self.overlay = None
        self.mouse_callback = None
        self.location_callback = None
        self._drag_key = None
        self._last_screen = None
        self._hover_key = None
        self._field_key = None
        self._drag_item_label = None
        self._anchor_segments = {}
        self._base_point = (0.0, 0.0, 0.0)
        self._rig_height = 1.0
        self.error = None

    @staticmethod
    def _coin() -> ModuleType:
        """Load the FreeCAD Coin/Pivy bindings lazily.

        Returns:
            The Coin module exposed by the installed Pivy runtime.
        """
        from pivy import coin

        return coin

    @staticmethod
    def _unit(vector: _Vector3) -> _Vector3:
        """Return a normalized three-dimensional vector, or a stable fallback.

        Args:
            vector: Three-dimensional vector to normalize.

        Returns:
            Unit vector in the supplied direction, or the positive Z axis when degenerate.
        """
        length = math.sqrt(sum(float(value) ** 2 for value in vector))
        if length <= 1e-9:
            return (0.0, 0.0, 1.0)
        return tuple(float(value) / length for value in vector)

    @staticmethod
    def _add(left: _Vector3, right: _Vector3) -> _Vector3:
        """Add two three-dimensional vectors.

        Args:
            left: First vector.
            right: Second vector.

        Returns:
            Component-wise vector sum.
        """
        return tuple(float(left[i]) + float(right[i]) for i in range(3))

    @staticmethod
    def _subtract(left: _Vector3, right: _Vector3) -> _Vector3:
        """Subtract one three-dimensional vector from another.

        Args:
            left: Vector from which the second vector is subtracted.
            right: Vector subtracted from the first vector.

        Returns:
            Component-wise vector difference.
        """
        return tuple(float(left[i]) - float(right[i]) for i in range(3))

    @staticmethod
    def _scale(vector: _Vector3, amount: float) -> _Vector3:
        """Scale a three-dimensional vector by a scalar.

        Args:
            vector: Vector to scale.
            amount: Scalar applied to each component.

        Returns:
            Scaled three-dimensional vector.
        """
        return tuple(float(value) * float(amount) for value in vector)

    @staticmethod
    def _dot(left: _Vector3, right: _Vector3) -> float:
        """Return the dot product of two three-dimensional vectors.

        Args:
            left: First vector.
            right: Second vector.

        Returns:
            Scalar dot product.
        """
        return sum(float(left[i]) * float(right[i]) for i in range(3))

    @staticmethod
    def _cross(left: _Vector3, right: _Vector3) -> _Vector3:
        """Return the cross product of two three-dimensional vectors.

        Args:
            left: First vector.
            right: Second vector.

        Returns:
            Three-dimensional cross product.
        """
        return (
            float(left[1]) * float(right[2]) - float(left[2]) * float(right[1]),
            float(left[2]) * float(right[0]) - float(left[0]) * float(right[2]),
            float(left[0]) * float(right[1]) - float(left[1]) * float(right[0]),
        )

    @classmethod
    def _orthogonal_radial(cls, normal: _Vector3, hint: _Vector3) -> _Vector3:
        """Choose a stable radial vector perpendicular to a ring's body axis.

        Args:
            normal: Direction along the measured body or limb segment.
            hint: Preferred outward/front direction.

        Returns:
            Unit radial vector in the plane perpendicular to the supplied normal.
        """
        axis = cls._unit(normal)
        projected = cls._subtract(hint, cls._scale(axis, cls._dot(hint, axis)))
        if math.sqrt(cls._dot(projected, projected)) <= 1e-8:
            reference = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.8 else (1.0, 0.0, 0.0)
            projected = cls._cross(axis, reference)
        return cls._unit(projected)

    @classmethod
    def _midpoint(cls, segment: _Segment) -> _Vector3:
        """Return the midpoint of one skeleton head/tail segment.

        Args:
            segment: Pair of three-dimensional head and tail positions.

        Returns:
            Midpoint in avatar model coordinates.
        """
        return cls._scale(cls._add(segment[0], segment[1]), 0.5)

    @classmethod
    def _lerp(cls, start: _Vector3, end: _Vector3, factor: float) -> _Vector3:
        """Interpolate a point along a skeleton segment.

        Args:
            start: First endpoint.
            end: Second endpoint.
            factor: Interpolation fraction between zero and one.

        Returns:
            Interpolated three-dimensional point.
        """
        return cls._add(start, cls._scale(cls._subtract(end, start), factor))

    @classmethod
    def _trunk_landmarks(cls, pelvis: _Vector3, chest: _Vector3) -> dict[str, _Vector3]:
        """Place torso guides along the actual pelvis-to-chest rig span.

        Adjacent spine-bone endpoints can be the same authored joint. Interpolate
        between the pelvis and chest control landmarks instead, so every torso
        circumference has a distinct, stable position.

        Args:
            pelvis: Fitted pelvis control point.
            chest: Fitted chest control point.

        Returns:
            Named trunk circumference centres from lower hip through chest.
        """
        return {
            "hip": pelvis,
            "high_hip": cls._lerp(pelvis, chest, 0.18),
            "waist": cls._lerp(pelvis, chest, 0.40),
            "stomach": cls._lerp(pelvis, chest, 0.60),
            "underbust": cls._lerp(pelvis, chest, 0.80),
            "chest": chest,
        }

    @classmethod
    def _ring_points(
        cls,
        center: _Vector3,
        normal: _Vector3,
        radial: _Vector3,
        radius: float,
        segments: int = RING_SEGMENTS,
    ) -> tuple[_Vector3, ...]:
        """Create a closed circle perpendicular to a measured body/limb axis.

        Args:
            center: Ring center in mannequin model coordinates.
            normal: Unit normal defining the ring plane.
            radial: Preferred in-plane radial direction.
            radius: Ring radius in millimetres.
            segments: Number of evenly spaced line segments.

        Returns:
            Closed sequence of three-dimensional points suitable for Coin SoLineSet.
        """
        axis = cls._unit(normal)
        first = cls._orthogonal_radial(axis, radial)
        second = cls._unit(cls._cross(axis, first))
        points = [
            cls._add(
                center,
                cls._add(
                    cls._scale(first, float(radius) * math.cos(2.0 * math.pi * index / segments)),
                    cls._scale(second, float(radius) * math.sin(2.0 * math.pi * index / segments)),
                ),
            )
            for index in range(segments)
        ]
        points.append(points[0])
        return tuple(points)

    def _build_anchor_segments(self) -> None:
        """Read anatomically authored joint positions from the current fitted avatar rig.

        Returns:
            Mapping of bone identifiers to transformed head/tail coordinates.

        Raises:
            RuntimeError: If the avatar does not expose a usable skeleton.
        """
        from freecad_cloth.avatar.AvatarPoseGui import skeleton_world_segments

        segments, _joints = skeleton_world_segments(self.panel._staged_parameters())
        if not segments:
            msg = "the fitted mannequin skeleton has no usable measurement landmarks"
            raise RuntimeError(msg)
        self._anchor_segments = segments
        feet = [segment[1] for name, segment in segments.items() if name in {"foot.L", "foot.R"}]
        points = [point for segment in segments.values() for point in segment]
        base_z = min((point[2] for point in feet), default=min(point[2] for point in points))
        base_x = sum(point[0] for point in feet) / len(feet) if feet else 0.0
        base_y = sum(point[1] for point in feet) / len(feet) if feet else 0.0
        self._base_point = (float(base_x), float(base_y), float(base_z))
        head = segments.get("head")
        top_z = max((point[2] for point in head), default=max(point[2] for point in points))
        self._rig_height = max(1.0, float(top_z) - float(base_z))

    def _scaled_segments(self, target_height: float) -> dict[str, _Segment]:
        """Scale cached rig landmarks around the foot plane to the staged body height.

        Args:
            target_height: Current staged height in millimetres.

        Returns:
            Skeleton segments scaled to match the numeric height target.
        """
        ratio = float(target_height) / self._rig_height
        base = self._base_point

        def transform(point: _Vector3) -> _Vector3:
            """Scale one landmark around the avatar's foot-plane origin."""
            return self._add(base, self._scale(self._subtract(point, base), ratio))

        return {
            name: (transform(segment[0]), transform(segment[1]))
            for name, segment in self._anchor_segments.items()
        }

    def _screen_position(self, point: _Vector3) -> _ScreenPoint:
        """Project a FreeCAD-space point into viewport coordinates with a top-left origin.

        Args:
            point: Three-dimensional model-space point.

        Returns:
            Two-dimensional screen coordinate.
        """
        projected = self.view.getPointOnScreen(self.App.Vector(*point))
        size = self.view.getSize()
        return float(projected[0]), float(size[1] - projected[1])

    def activate(self) -> bool:
        """Install the transient surface guides and viewport callbacks.

        Returns:
            True when the dimension controls were installed successfully.
        """
        if self.view is not None:
            return True
        if self.panel.avatar is None or self.panel._provider_id() != "makehuman-hm08":
            return False
        try:
            coin = self._coin()
            active = self.Gui.activeDocument()
            if active is None:
                return False
            self.view = active.activeView()
            self.scene_graph = self.view.getSceneGraph()
            self.overlay = coin.SoSeparator()
            self.overlay.setName("ClothAvatarDimensionOverlay")
            depth = coin.SoDepthBuffer()
            depth.test = False
            depth.write = False
            self.overlay.addChild(depth)
            self._build_anchor_segments()
            self.scene_graph.addChild(self.overlay)
            self.mouse_callback = self.view.addEventCallbackPivy(
                coin.SoMouseButtonEvent.getClassTypeId(), self._mouse_event
            )
            self.location_callback = self.view.addEventCallbackPivy(
                coin.SoLocation2Event.getClassTypeId(), self._location_event
            )
            self.refresh(force=True)
            self.error = None
            return True
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as exc:
            self.error = repr(exc)
            self.deactivate()
            return False

    def deactivate(self) -> None:
        """Remove the overlay and every event callback owned by this controller."""
        view = self.view
        if view is not None:
            with contextlib.suppress(AttributeError, RuntimeError, TypeError):
                coin = self._coin()
                if self.mouse_callback is not None:
                    view.removeEventCallbackPivy(
                        coin.SoMouseButtonEvent.getClassTypeId(), self.mouse_callback
                    )
                if self.location_callback is not None:
                    view.removeEventCallbackPivy(
                        coin.SoLocation2Event.getClassTypeId(), self.location_callback
                    )
        if self.scene_graph is not None and self.overlay is not None:
            with contextlib.suppress(AttributeError, RuntimeError, TypeError):
                self.scene_graph.removeChild(self.overlay)
        self.view = None
        self.scene_graph = None
        self.overlay = None
        self.mouse_callback = None
        self.location_callback = None
        self._drag_key = None
        self._last_screen = None
        self._hover_key = None
        self._field_key = None
        self._drag_item_label = None
        self.panel._set_measurement_hover(None)

    def _add_line(
        self,
        coin: ModuleType,
        points: Sequence[_Vector3],
        color: _Vector3,
        width: float = 1.4,
        *,
        depth_test: bool = False,
    ) -> None:
        """Add a transient line with an explicit mesh depth-test policy.

        Args:
            coin: Pivy Coin module supplying scene-graph types.
            points: Ordered model-space line vertices.
            color: Normalized RGB line color.
            width: Line width in viewport pixels.
            depth_test: True to let the mannequin occlude the guide line.
        """
        separator = coin.SoSeparator()
        depth = coin.SoDepthBuffer()
        depth.test = bool(depth_test)
        depth.write = False
        draw = coin.SoDrawStyle()
        draw.lineWidth = float(width)
        base = coin.SoBaseColor()
        base.rgb = color
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, len(points), points)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(points))
        separator.addChild(depth)
        separator.addChild(draw)
        separator.addChild(base)
        separator.addChild(coordinates)
        separator.addChild(line)
        self.overlay.addChild(separator)

    def _add_marker(
        self, coin: ModuleType, point: _Vector3, color: _Vector3, size: float
    ) -> None:
        """Draw an always-pickable foreground marker at a dimensional handle.

        Args:
            coin: Pivy Coin module supplying scene-graph types.
            point: Three-dimensional handle position.
            color: Normalized RGB marker color.
            size: Marker diameter in viewport pixels.
        """
        marker = coin.SoSeparator()
        depth = coin.SoDepthBuffer()
        depth.test = False
        depth.write = False
        draw = coin.SoDrawStyle()
        draw.pointSize = float(size)
        base = coin.SoBaseColor()
        base.rgb = color
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, 1, [point])
        points = coin.SoPointSet()
        points.numPoints = 1
        marker.addChild(depth)
        marker.addChild(draw)
        marker.addChild(base)
        marker.addChild(coordinates)
        marker.addChild(points)
        self.overlay.addChild(marker)

    def _add_label(
        self, coin: ModuleType, point: _Vector3, label: str, color: _Vector3
    ) -> None:
        """Draw the one-line value tooltip for the currently linked dimension.

        Args:
            coin: Pivy Coin module supplying scene-graph types.
            point: World-space label origin.
            label: Concise measurement name and current value.
            color: Normalized RGB text color.
        """
        separator = coin.SoSeparator()
        depth = coin.SoDepthBuffer()
        depth.test = False
        depth.write = False
        translation = coin.SoTranslation()
        translation.translation.setValue(
            coin.SbVec3f(float(point[0] + 15.0), float(point[1]), float(point[2] + 12.0))
        )
        base = coin.SoBaseColor()
        base.rgb = color
        text = coin.SoText2()
        text.string.setValue(str(label))
        separator.addChild(depth)
        separator.addChild(translation)
        separator.addChild(base)
        separator.addChild(text)
        self.overlay.addChild(separator)

    def _specs(self, *, force: bool = False) -> tuple[_DimensionSpec, ...]:
        """Build current handle geometry from staged values and fitted rig landmarks.

        Args:
            force: Recompute the skeleton anchors from the current staged avatar.

        Returns:
            All visible measurement handles, including paired left/right limb controls.
        """
        if force or not self._anchor_segments:
            self._build_anchor_segments()
        from freecad_cloth.avatar.AvatarModel import LIMITS

        measurements = self.panel._staged_parameters().measurements
        height = float(measurements["height"])
        segments = self._scaled_segments(height)

        def segment(name: str) -> _Segment | None:
            """Return one transformed bone segment or None when the rig omits it."""
            return segments.get(name)

        def midpoint(name: str) -> _Vector3 | None:
            """Return one transformed bone midpoint or None when unavailable."""
            value = segment(name)
            return None if value is None else self._midpoint(value)

        pelvis = midpoint("spine05") or self._base_point
        chest = midpoint("spine03") or pelvis
        neck = midpoint("neck01") or chest
        body_axis = self._unit(self._subtract(neck, pelvis))
        trunk_centers = self._trunk_landmarks(pelvis, chest)
        specs: list[_DimensionSpec] = []

        def add_ring(
            key: str,
            label: str,
            center: _Vector3 | None,
            normal: _Vector3,
            radial_hint: _Vector3,
        ) -> None:
            """Append a value-scaled circumference guide around an authored rig point."""
            if center is None:
                return
            axis = self._unit(normal)
            radial = self._orthogonal_radial(axis, radial_hint)
            radius = float(measurements[key]) / (2.0 * math.pi)
            point = self._add(center, self._scale(radial, radius))
            specs.append(
                {
                    "key": key,
                    "label": label,
                    "shape": "ring",
                    "center": center,
                    "normal": axis,
                    "radial": radial,
                    "radius": radius,
                    "point": point,
                    "axis": radial,
                    "multiplier": 2.0 * math.pi,
                    "bounds": LIMITS[key],
                }
            )

        # The trunk landmarks are actual spine/neck joints, not percentages of total height.
        add_ring("neck", "Neck", neck, body_axis, (0.0, 1.0, 0.0))
        for key, label in (
            ("chest", "Chest / bust"),
            ("underbust", "Underbust"),
            ("stomach", "Stomach"),
            ("waist", "Waist"),
            ("high_hip", "High hip"),
            ("hip", "Hip"),
        ):
            add_ring(key, label, trunk_centers[key], body_axis, (0.0, 1.0, 0.0))

        shoulder_left = segment("upperarm01.L")
        shoulder_right = segment("upperarm01.R")
        if shoulder_left is not None and shoulder_right is not None:
            left_point = shoulder_left[0]
            right_point = shoulder_right[0]
            center = self._midpoint((left_point, right_point))
            span_axis = self._unit(self._subtract(right_point, left_point))
            if span_axis[0] < 0.0:
                span_axis = self._scale(span_axis, -1.0)
            half_width = float(measurements["shoulder"]) / 2.0
            endpoints = (
                self._subtract(center, self._scale(span_axis, half_width)),
                self._add(center, self._scale(span_axis, half_width)),
            )
            specs.append(
                {
                    "key": "shoulder",
                    "label": "Shoulder breadth",
                    "shape": "line",
                    "line": endpoints,
                    "point": endpoints[1],
                    "axis": span_axis,
                    "multiplier": 2.0,
                    "bounds": LIMITS["shoulder"],
                }
            )

        # Limb circumference fields are shared between sides; either ring edits the same value.
        for side, side_label in (("L", "Left"), ("R", "Right")):
            arm = segment(f"upperarm01.{side}")
            forearm = segment(f"lowerarm01.{side}")
            wrist = segment(f"wrist.{side}")
            thigh = segment(f"upperleg01.{side}")
            lower_leg = segment(f"lowerleg01.{side}")
            foot = segment(f"foot.{side}")

            if arm is not None:
                arm_center = self._midpoint(arm)
                add_ring(
                    "upper_arm",
                    f"{side_label} upper arm",
                    arm_center,
                    self._subtract(arm[1], arm[0]),
                    self._subtract(arm_center, chest),
                )
            if forearm is not None:
                elbow_center = forearm[0]
                forearm_axis = self._subtract(forearm[1], forearm[0])
                add_ring(
                    "elbow",
                    f"{side_label} elbow",
                    elbow_center,
                    forearm_axis,
                    self._subtract(elbow_center, chest),
                )
                wrist_center = self._midpoint(wrist) if wrist is not None else forearm[1]
                add_ring(
                    "wrist",
                    f"{side_label} wrist",
                    wrist_center,
                    forearm_axis,
                    self._subtract(wrist_center, chest),
                )
            if thigh is not None:
                thigh_center = self._midpoint(thigh)
                add_ring(
                    "thigh",
                    f"{side_label} thigh",
                    thigh_center,
                    self._subtract(thigh[1], thigh[0]),
                    self._subtract(thigh_center, pelvis),
                )
            if lower_leg is not None:
                lower_axis = self._subtract(lower_leg[1], lower_leg[0])
                add_ring(
                    "knee",
                    f"{side_label} knee",
                    lower_leg[0],
                    lower_axis,
                    self._subtract(lower_leg[0], pelvis),
                )
                add_ring(
                    "calf",
                    f"{side_label} calf",
                    self._midpoint(lower_leg),
                    lower_axis,
                    self._subtract(self._midpoint(lower_leg), pelvis),
                )
                ankle_center = foot[0] if foot is not None else lower_leg[1]
                add_ring(
                    "ankle",
                    f"{side_label} ankle",
                    ankle_center,
                    lower_axis,
                    self._subtract(ankle_center, pelvis),
                )

            if arm is not None and forearm is not None:
                sleeve_start = arm[0]
                sleeve_direction = self._unit(self._subtract(forearm[1], sleeve_start))
                sleeve_end = self._add(
                    sleeve_start,
                    self._scale(sleeve_direction, float(measurements["sleeve_length"])),
                )
                specs.append(
                    {
                        "key": "sleeve_length",
                        "label": f"{side_label} sleeve length",
                        "shape": "line",
                        "line": (sleeve_start, sleeve_end),
                        "point": sleeve_end,
                        "axis": sleeve_direction,
                        "multiplier": 1.0,
                        "bounds": LIMITS["sleeve_length"],
                    }
                )

        feet = [segments[name][1] for name in ("foot.L", "foot.R") if name in segments]
        base = self._base_point
        if feet:
            base = (
                sum(point[0] for point in feet) / len(feet),
                sum(point[1] for point in feet) / len(feet),
                min(point[2] for point in feet),
            )
        height_point = self._add(base, (0.0, 0.0, height))
        specs.insert(
            0,
            {
                "key": "height",
                "label": "Height",
                "shape": "line",
                "line": (base, height_point),
                "point": height_point,
                "axis": (0.0, 0.0, 1.0),
                "multiplier": 1.0,
                "bounds": LIMITS["height"],
            },
        )
        return tuple(specs)

    def refresh(self, *, force: bool = False) -> None:
        """Redraw value-driven handles and mesh-occluded guide rings.

        Args:
            force: Recompute the rig landmarks after a committed avatar rebuild.
        """
        if self.view is None or self.scene_graph is None or self.overlay is None:
            return
        try:
            coin = self._coin()
            while self.overlay.getNumChildren() > 1:
                self.overlay.removeChild(1)
            from freecad_cloth.shared.ViewportGizmoStyle import (
                ACTIVE_COLOR,
                DIMENSION_GUIDE_COLOR,
                DIMENSION_GUIDE_LINE_WIDTH,
                RIG_EDITABLE_COLOR,
            )

            specs = self._specs(force=force)
            measurements = self.panel._staged_parameters().measurements
            active_keys = {self._hover_key, self._field_key}
            active_keys.discard(None)
            for item in specs:
                key = item["key"]
                color = ACTIVE_COLOR if key in active_keys else DIMENSION_GUIDE_COLOR
                width = DIMENSION_GUIDE_LINE_WIDTH + (0.8 if key in active_keys else 0.0)
                if item["shape"] == "ring":
                    points = self._ring_points(
                        item["center"],
                        item["normal"],
                        item["radial"],
                        item["radius"],
                        self.RING_SEGMENTS,
                    )
                    self._add_line(coin, points, color, width, depth_test=True)
                else:
                    self._add_line(
                        coin,
                        item["line"],
                        RIG_EDITABLE_COLOR if key not in active_keys else ACTIVE_COLOR,
                        width,
                        depth_test=True,
                    )
                self._add_marker(
                    coin,
                    item["point"],
                    ACTIVE_COLOR if key in active_keys else RIG_EDITABLE_COLOR,
                    12.0 if key in active_keys else 8.0,
                )
                if key in active_keys:
                    self._add_label(
                        coin,
                        item["point"],
                        f"{item['label']}  {float(measurements[key]):.1f} mm",
                        ACTIVE_COLOR,
                    )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            # Numeric controls remain usable if a host FreeCAD build lacks a Coin API.
            return

    def set_field_focus(self, key: str | None) -> None:
        """Highlight the matching viewport control while its numeric field has focus.

        Args:
            key: Canonical measurement key, or None when no linked field is focused.
        """
        self._field_key = None if key is None else str(key)
        self.refresh()

    def _screen_axis(self, item: _DimensionSpec) -> _ScreenPoint:
        """Return the screen-space direction used to manipulate one handle.

        Args:
            item: Dimension handle description from _specs.

        Returns:
            Projected two-dimensional axis vector.
        """
        point = item["point"]
        axis = item["axis"]
        origin = self._screen_position(point)
        end = self._screen_position(
            (
                point[0] + axis[0] * self.DRAG_AXIS_LENGTH,
                point[1] + axis[1] * self.DRAG_AXIS_LENGTH,
                point[2] + axis[2] * self.DRAG_AXIS_LENGTH,
            )
        )
        return (end[0] - origin[0], end[1] - origin[1])

    @staticmethod
    def _distance(point_a: _ScreenPoint, point_b: _ScreenPoint) -> float:
        """Return Euclidean viewport distance in pixels.

        Args:
            point_a: First screen-space point.
            point_b: Second screen-space point.

        Returns:
            Distance in viewport pixels.
        """
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    def _pick(self, screen: _ScreenPoint) -> _DimensionSpec | None:
        """Pick the nearest dimension marker, rejecting clicks away from controls.

        Args:
            screen: Mouse position in top-left-origin viewport coordinates.

        Returns:
            Nearest handle description within the pick radius, or None.
        """
        best = None
        distance = self.HIT_RADIUS
        for item in self._specs():
            point = self._screen_position(item["point"])
            candidate = self._distance(screen, point)
            if candidate < distance:
                best = item
                distance = candidate
        return best

    @staticmethod
    def _dragged_value(
        current: float,
        delta_screen: tuple[float, float],
        projected_axis: tuple[float, float],
        multiplier: float,
        bounds: tuple[float, float],
        axis_length: float = 100.0,
    ) -> float:
        """Convert viewport motion into a clamped millimetre measurement.

        Args:
            current: Current staged measurement value.
            delta_screen: Pointer movement since the previous event.
            projected_axis: Screen projection of the world-space drag axis.
            multiplier: Circumference or bilateral-width conversion multiplier.
            bounds: Minimum and maximum values from the avatar measurement model.
            axis_length: World-space length represented by the projected axis.

        Returns:
            Updated measurement clamped to its authoritative model limits.
        """
        denominator = projected_axis[0] ** 2 + projected_axis[1] ** 2
        if denominator <= 1e-8:
            return float(current)
        delta_world = (
            (delta_screen[0] * projected_axis[0] + delta_screen[1] * projected_axis[1])
            * float(axis_length)
            / denominator
        )
        low, high = bounds
        return max(float(low), min(float(high), float(current) + delta_world * multiplier))

    def _location_event(self, event_callback: _CoinEventCallbackProtocol) -> None:
        """Track dimension hover and update the value while a handle is dragged.

        Args:
            event_callback: Coin callback exposing the current mouse position.
        """
        event = event_callback.getEvent()
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        if self._drag_key is not None:
            item = next(
                (part for part in self._specs() if part["label"] == self._drag_item_label),
                None,
            )
            if item is None or self._last_screen is None:
                return
            try:
                axis = self._screen_axis(item)
                delta_screen = (
                    screen[0] - self._last_screen[0],
                    screen[1] - self._last_screen[1],
                )
                current = float(self.panel._boxes[self._drag_key].value())
                candidate = self._dragged_value(
                    current,
                    delta_screen,
                    axis,
                    float(item["multiplier"]),
                    item["bounds"],
                    self.DRAG_AXIS_LENGTH,
                )
                self.panel._boxes[self._drag_key].setValue(candidate)
                self._last_screen = screen
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return
            return

        picked = self._pick(screen)
        key = None if picked is None else picked["key"]
        if key != self._hover_key:
            self._hover_key = key
            self.panel._set_measurement_hover(key)
            self.refresh()

    def _mouse_event(self, event_callback: _CoinEventCallbackProtocol) -> None:
        """Start or end a direct measurement drag from a visible viewport marker.

        Args:
            event_callback: Coin callback exposing the mouse-button event.
        """
        coin = self._coin()
        event = event_callback.getEvent()
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        if event.getState() == coin.SoMouseButtonEvent.UP:
            if self._drag_key is not None:
                self._drag_key = None
                self._last_screen = None
                self._drag_item_label = None
                self.refresh()
                self.panel._set_status(
                    "Measurement staged. The linked field shows the exact value; "
                    "Apply & Rebuild commits it.",
                    state="success",
                )
            return
        if (
            event.getState() != coin.SoMouseButtonEvent.DOWN
            or event.getButton() != coin.SoMouseButtonEvent.BUTTON1
            or self._drag_key is not None
        ):
            return
        item = self._pick(screen)
        if item is None:
            return
        self._drag_key = item["key"]
        self._drag_item_label = item["label"]
        self._last_screen = screen
        self._hover_key = item["key"]
        self.panel._set_measurement_hover(item["key"])
        self.panel._focus_measurement(item["key"])
        self.refresh()
        self.panel._set_status(
            f"Dragging {item['label'].lower()} — release to stage the value.",
            state="info",
        )
        with contextlib.suppress(AttributeError, RuntimeError):
            event_callback.setHandled()

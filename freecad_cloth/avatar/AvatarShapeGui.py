# Copyright (C) 2026 FreeCAD Cloth contributors
"""Transient viewport dimension handles for the staged mannequin editor.

The handles only edit staged task-panel values. They are Coin3D overlay nodes,
never FreeCAD document objects, and their callbacks are removed when the editor
closes so they cannot interfere with the independent 3D Pattern Pen tool.
"""

from __future__ import annotations

import contextlib
import math


class AvatarDimensionController:
    """Show and drag measurement handles in the active FreeCAD viewport."""

    HIT_RADIUS = 24.0
    RING_SEGMENTS = 64
    DRAG_AXIS_LENGTH = 100.0

    def __init__(self, panel):
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
        self.error = None

    @staticmethod
    def _coin():
        """Load the FreeCAD Coin/Pivy bindings lazily."""
        from pivy import coin

        return coin

    def _screen_position(self, point):
        """Project one FreeCAD-space point into the viewport's top-left origin."""
        projected = self.view.getPointOnScreen(self.App.Vector(*point))
        size = self.view.getSize()
        return float(projected[0]), float(size[1] - projected[1])

    def _specs(self):
        """Return visible dimension handles derived from staged numeric values."""
        from freecad_cloth.avatar.AvatarModel import LIMITS

        params = self.panel._staged_parameters()
        m = params.measurements
        height = float(m["height"])
        specs = [
            ("height", "Height", (0.0, 0.0, height), (0.0, 0.0, 1.0), 1.0),
            (
                "shoulder",
                "Shoulder",
                (float(m["shoulder"]) / 2.0, 0.0, height * 0.77),
                (1.0, 0.0, 0.0),
                2.0,
            ),
        ]
        for key, label, level in (
            ("chest", "Chest", 0.69),
            ("waist", "Waist", 0.58),
            ("hip", "Hip", 0.50),
        ):
            radius = float(m[key]) / (2.0 * math.pi)
            specs.append(
                (key, label, (radius, 0.0, height * level), (1.0, 0.0, 0.0), 2.0 * math.pi)
            )
        return tuple(
            {
                "key": key,
                "label": label,
                "point": point,
                "axis": axis,
                "multiplier": multiplier,
                "bounds": LIMITS[key],
            }
            for key, label, point, axis, multiplier in specs
        )

    def activate(self):
        """Install the transient overlay and viewport callbacks; return success."""
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
            self.scene_graph.addChild(self.overlay)
            self.mouse_callback = self.view.addEventCallbackPivy(
                coin.SoMouseButtonEvent.getClassTypeId(), self._mouse_event
            )
            self.location_callback = self.view.addEventCallbackPivy(
                coin.SoLocation2Event.getClassTypeId(), self._location_event
            )
            self.refresh()
            self.error = None
            return True
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as exc:
            self.error = repr(exc)
            self.deactivate()
            return False

    def deactivate(self):
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

    def _add_line(self, coin, points, color, width=1.4):
        """Add a single depth-independent polyline to the transient overlay."""
        separator = coin.SoSeparator()
        draw = coin.SoDrawStyle()
        draw.lineWidth = float(width)
        base = coin.SoBaseColor()
        base.rgb = color
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, len(points), points)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(points))
        separator.addChild(draw)
        separator.addChild(base)
        separator.addChild(coordinates)
        separator.addChild(line)
        self.overlay.addChild(separator)

    def _add_label(self, coin, point, label, color):
        """Add an always-visible short name adjacent to a dimension handle."""
        separator = coin.SoSeparator()
        translation = coin.SoTranslation()
        translation.translation.setValue(
            coin.SbVec3f(float(point[0] + 18.0), float(point[1]), float(point[2] + 10.0))
        )
        base = coin.SoBaseColor()
        base.rgb = color
        text = coin.SoText2()
        text.string.setValue(str(label))
        separator.addChild(translation)
        separator.addChild(base)
        separator.addChild(text)
        self.overlay.addChild(separator)

    def refresh(self):
        """Redraw dimensions from current staged values without adding document objects."""
        if self.view is None or self.scene_graph is None or self.overlay is None:
            return
        try:
            coin = self._coin()
            while self.overlay.getNumChildren() > 1:
                self.overlay.removeChild(1)
            from freecad_cloth.shared.viewport_gizmo_style import (
                ACTIVE_COLOR,
                RIG_PASSIVE_COLOR,
                SNAP_TARGET_COLOR,
            )

            specs = self._specs()
            by_key = {item["key"]: item for item in specs}
            m = self.panel._staged_parameters().measurements
            height = float(m["height"])
            self._add_line(
                coin,
                ((0.0, 0.0, 0.0), (0.0, 0.0, height)),
                RIG_PASSIVE_COLOR,
                1.6,
            )
            shoulder = float(m["shoulder"]) / 2.0
            self._add_line(
                coin,
                ((-shoulder, 0.0, height * 0.77), (shoulder, 0.0, height * 0.77)),
                RIG_PASSIVE_COLOR,
                1.6,
            )
            for key in ("chest", "waist", "hip"):
                handle = by_key[key]["point"]
                radius = float(m[key]) / (2.0 * math.pi)
                level = handle[2]
                ring = [
                    (
                        radius * math.cos(2.0 * math.pi * index / self.RING_SEGMENTS),
                        radius * math.sin(2.0 * math.pi * index / self.RING_SEGMENTS),
                        level,
                    )
                    for index in range(self.RING_SEGMENTS)
                ]
                ring.append(ring[0])
                color = (
                    ACTIVE_COLOR
                    if self._hover_key == key or self._drag_key == key
                    else SNAP_TARGET_COLOR
                )
                self._add_line(coin, ring, color, 2.4 if color == ACTIVE_COLOR else 1.5)

            for item in specs:
                key = item["key"]
                point = item["point"]
                color = (
                    ACTIVE_COLOR
                    if self._hover_key == key or self._drag_key == key
                    else SNAP_TARGET_COLOR
                )
                self._add_line(
                    coin,
                    (
                        point,
                        (
                            point[0] + item["axis"][0] * 26.0,
                            point[1] + item["axis"][1] * 26.0,
                            point[2] + item["axis"][2] * 26.0,
                        ),
                    ),
                    color,
                    2.4,
                )
                marker = coin.SoSeparator()
                draw = coin.SoDrawStyle()
                draw.pointSize = 11.0 if color == ACTIVE_COLOR else 8.0
                base = coin.SoBaseColor()
                base.rgb = color
                coord = coin.SoCoordinate3()
                coord.point.setValues(0, 1, [point])
                points = coin.SoPointSet()
                points.numPoints = 1
                marker.addChild(draw)
                marker.addChild(base)
                marker.addChild(coord)
                marker.addChild(points)
                self.overlay.addChild(marker)
                value = float(m["height"]) if key == "height" else float(m[key])
                label = item["label"]
                if self._hover_key == key or self._drag_key == key:
                    label = f"{label}  {value:.0f} mm"
                self._add_label(coin, point, label, color)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            # Numeric fields remain available if a FreeCAD build lacks a Coin API.
            return

    def _screen_axis(self, item):
        """Return the screen-space direction corresponding to the handle's world axis."""
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
    def _distance(point_a, point_b):
        """Return Euclidean viewport distance in pixels."""
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    def _pick(self, screen):
        """Pick the nearest dimension handle, rejecting clicks away from controls."""
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
        """Convert a viewport drag into a clamped millimetre measurement."""
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

    def _location_event(self, event_callback):
        """Track handle hover and apply motion while the user drags a dimension."""
        event = event_callback.getEvent()
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        if self._drag_key is not None:
            item = next((part for part in self._specs() if part["key"] == self._drag_key), None)
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
            self.refresh()

    def _mouse_event(self, event_callback):
        """Start or end a staged dimension drag from a visible handle."""
        coin = self._coin()
        event = event_callback.getEvent()
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        if event.getState() == coin.SoMouseButtonEvent.UP:
            if self._drag_key is not None:
                self._drag_key = None
                self._last_screen = None
                self.refresh()
                self.panel._refresh_status(
                    "Dimension drag staged. Apply & Rebuild commits it; Cancel discards it."
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
        self._last_screen = screen
        self._hover_key = item["key"]
        self.refresh()
        self.panel.status.setText(
            "Dragging {} — release to stage the value; Apply & Rebuild commits it.".format(
                item["label"].lower()
            )
        )
        with contextlib.suppress(AttributeError, RuntimeError):
            event_callback.setHandled()

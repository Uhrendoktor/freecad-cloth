"""Direct-manipulation fitting UI for the Cloth Sewing workbench.

The fitting scene remains authoritative; viewport movement is an interactive
frontend that commits final placements through FittingCommands. Numeric
placement values are deliberately absent from the normal workflow and remain
available through FreeCAD's property editor for precision work.
"""

import contextlib
import math

from freecad_cloth.shared.viewport_gizmo_style import (
    SNAP_CENTER_RADIUS,
    SNAP_CROSSHAIR_HALF_LENGTH,
    SNAP_LINE_WIDTH,
    SNAP_RING_RADIUS,
    SNAP_RING_SEGMENTS,
    SNAP_STALE_COLOR,
    SNAP_TARGET_COLOR,
)


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


def coin_position_to_screen(position, viewport_height):
    """Convert Coin's bottom-left-origin event point to top-left screen coordinates."""
    return float(position[0]), float(viewport_height) - float(position[1])


def nearest_arrangement_point(position, points, max_distance):
    """Return the nearest 2D arrangement point within the supplied distance.

    position is an (x, y) pair and every point is an object exposing
    X and Y attributes. The helper is GUI-neutral so snap behavior can
    be tested without importing FreeCAD.
    """
    px, py = float(position[0]), float(position[1])
    best = None
    best_distance = float(max_distance)
    for point in points:
        dx = float(point.X) - px
        dy = float(point.Y) - py
        distance = (dx * dx + dy * dy) ** 0.5
        if distance <= best_distance:
            best = point
            best_distance = distance
    return best


class SimpleScreenPoint:
    """GUI-neutral screen-space adapter for a persistent arrangement point."""

    def __init__(self, x, y, source):
        self.X = float(x)
        self.Y = float(y)
        self.source = source


def arrangement_rotation(point):
    """Return the Z rotation implied by an arrangement point wrap direction."""

    base = float(getattr(point, "RotationZ", 0.0))
    return {
        "front": base,
        "back": base + 180.0,
        "left": base + 90.0,
        "right": base - 90.0,
    }.get(str(getattr(point, "WrapDirection", "front")), base)


def _xray_overlay(coin, name):
    """Create a Coin overlay that is not occluded by model geometry."""
    overlay = coin.SoSeparator()
    overlay.setName(name)
    depth = coin.SoDepthBuffer()
    depth.test = False
    depth.write = False
    overlay.addChild(depth)
    return overlay


def _billboard_marker(coin, position, color_rgb):
    """Create a camera-facing ring/crosshair centered at a world-space point."""
    marker = coin.SoSeparator()
    transform = coin.SoTransform()
    transform.translation.setValue(
        coin.SbVec3f(float(position[0]), float(position[1]), float(position[2]))
    )
    marker.addChild(transform)

    billboard = coin.SoBillboard()
    marker.addChild(billboard)
    glyph = coin.SoSeparator()
    draw_style = coin.SoDrawStyle()
    draw_style.lineWidth = SNAP_LINE_WIDTH
    color = coin.SoBaseColor()
    color.rgb = color_rgb
    glyph.addChild(draw_style)
    glyph.addChild(color)

    def add_polyline(points):
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, len(points), points)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(points))
        glyph.addChild(coordinates)
        glyph.addChild(line)

    radius = SNAP_RING_RADIUS
    ring = [
        coin.SbVec3f(
            radius * math.cos(index * 2.0 * math.pi / SNAP_RING_SEGMENTS),
            radius * math.sin(index * 2.0 * math.pi / SNAP_RING_SEGMENTS),
            0.0,
        )
        for index in range(SNAP_RING_SEGMENTS + 1)
    ]
    add_polyline(ring)

    center = coin.SoSphere()
    center.radius = SNAP_CENTER_RADIUS
    glyph.addChild(center)
    arm = SNAP_CROSSHAIR_HALF_LENGTH
    add_polyline([coin.SbVec3f(-arm, 0.0, 0.0), coin.SbVec3f(arm, 0.0, 0.0)])
    add_polyline([coin.SbVec3f(0.0, -arm, 0.0), coin.SbVec3f(0.0, arm, 0.0)])
    billboard.addChild(glyph)
    return marker


class DirectArrangeController:
    """Manage temporary FreeCAD viewport dragging and arrangement-point snapping."""

    SNAP_PIXEL_RADIUS = 36.0
    DRAG_PIXEL_THRESHOLD = 4.0

    def __init__(self, scene, status_callback=None, snap_enabled=True):
        self.App, self.Gui, self.QtCore, self.QtWidgets = _modules()
        self.scene = scene
        self.view = None
        self.status_callback = status_callback or (lambda _message: None)
        self.snap_enabled = bool(snap_enabled)
        self.drag_piece = None
        self.drag_start_screen = None
        self.drag_start_world = None
        self.drag_start_base = None
        self.drag_start_rotation = 0.0
        self.snap_point = None
        self._mouse_callback = None
        self._location_callback = None
        self._transaction_open = False
        self._snap_indicator = None
        self._pending_snap_point = None
        self._snap_indicator_update_pending = False
        self._snap_indicator_generation = 0
        self._anchor_overlay = None
        self._anchor_overlay_signature = None
        self._anchor_visibility = {}

    def _status(self, message):
        self.status_callback(str(message))

    def _points(self):
        if self.scene is None:
            return ()
        result = []
        document = getattr(self.scene, "Document", None)
        if document is None:
            return ()
        from freecad_cloth.avatar.FittingCommands import (
            _refresh_anchor_positions,
            arrangement_anchor_status,
        )

        _refresh_anchor_positions(self.scene, update_visuals=True)
        self._refresh_anchor_overlay(positions_refreshed=True)
        for name in tuple(getattr(self.scene, "ArrangementPointObjects", ()) or ()):
            obj = document.getObject(str(name))
            if obj is None or getattr(obj, "FittingType", "") != "ArrangementPoint":
                continue
            status = arrangement_anchor_status(obj)
            obj.AnchorStatus = status
            if status in {
                "stale",
                "missing target",
                "invalid",
                "wrong target",
                "unconfigured target",
            }:
                obj.Label = "Stale anchor: " + str(getattr(obj, "PointName", name))
                obj.ViewObject.ShapeColor = (0.95, 0.24, 0.16)
                obj.ViewObject.LineColor = (0.65, 0.10, 0.08)
                continue
            result.append(obj)
        return tuple(result)

    def _event_position(self, info):
        value = info.get("Position", (0, 0))
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError, IndexError):
            return None

    def _piece_from_info(self, info):
        document = getattr(self.scene, "Document", None)
        if document is None:
            return None
        wanted = {
            str(info.get("Object", "")),
            str(info.get("Name", "")),
        }
        for obj in document.Objects:
            if getattr(obj, "PatternType", "") != "PatternPiece":
                continue
            if str(getattr(obj, "Name", "")) in wanted or str(getattr(obj, "Label", "")) in wanted:
                return obj
        selected = tuple(
            obj
            for obj in self.Gui.Selection.getSelection()
            if getattr(obj, "PatternType", "") == "PatternPiece"
        )
        return selected[0] if len(selected) == 1 else None

    def _screen_position(self, point):
        projected = self.view.getPointOnScreen(
            self.App.Vector(float(point.X), float(point.Y), float(point.Offset))
        )
        size = self.view.getSize()
        return float(projected[0]), float(size[1] - projected[1])

    def _nearest_snap_point(self, screen_position):
        candidates = []
        for point in self._points():
            try:
                sx, sy = self._screen_position(point)
            except (AttributeError, TypeError, ValueError, RuntimeError):
                continue
            candidates.append((sx, sy, point))
        if not candidates:
            return None
        point = nearest_arrangement_point(
            screen_position,
            tuple(SimpleScreenPoint(sx, sy, point) for sx, sy, point in candidates),
            self.SNAP_PIXEL_RADIUS,
        )
        return getattr(point, "source", None)

    def _clear_snap_indicator(self):
        if self._snap_indicator is None or self.view is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError):
            self.view.getSceneGraph().removeChild(self._snap_indicator)
        self._snap_indicator = None

    def _show_snap_indicator(self, point):
        if self.view is None or point is None:
            self._clear_snap_indicator()
            return
        try:
            from pivy import coin

            self._clear_snap_indicator()
            separator = _xray_overlay(coin, "ClothArrangeSnapIndicator")
            separator.addChild(
                _billboard_marker(
                    coin,
                    (float(point.X), float(point.Y), float(point.Offset)),
                    SNAP_TARGET_COLOR,
                )
            )
            self.view.getSceneGraph().addChild(separator)
            self._snap_indicator = separator
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
            self._snap_indicator = None

    def _clear_anchor_overlay(self):
        """Remove the transient camera-facing anchor marker scene graph."""
        overlay = self._anchor_overlay
        self._anchor_overlay = None
        self._anchor_overlay_signature = None
        if overlay is None or self.view is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError):
            self.view.getSceneGraph().removeChild(overlay)

    def _hide_anchor_feature_objects(self, objects):
        """Hide model-space marker features while their viewport overlays are active."""
        for obj in objects:
            name = str(getattr(obj, "Name", "") or "")
            view_object = getattr(obj, "ViewObject", None)
            if not name or view_object is None:
                continue
            if name not in self._anchor_visibility:
                try:
                    self._anchor_visibility[name] = bool(view_object.Visibility)
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    continue
            try:
                if bool(view_object.Visibility):
                    view_object.Visibility = False
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue

    def _restore_anchor_feature_visibility(self):
        """Restore each persistent point object's visibility when Arrange closes."""
        document = getattr(self.scene, "Document", None)
        for name, visible in tuple(self._anchor_visibility.items()):
            if document is None:
                break
            obj = document.getObject(str(name))
            view_object = getattr(obj, "ViewObject", None) if obj is not None else None
            if view_object is None:
                continue
            with contextlib.suppress(AttributeError, RuntimeError, TypeError, ValueError):
                view_object.Visibility = bool(visible)
        self._anchor_visibility.clear()

    def _refresh_anchor_overlay(self, positions_refreshed=False):
        """Render every arrangement anchor as a visible, camera-facing viewport glyph."""
        if self.view is None:
            return
        document = getattr(self.scene, "Document", None)
        if document is None:
            self._clear_anchor_overlay()
            return
        try:
            from pivy import coin
            from freecad_cloth.avatar.FittingCommands import (
                _refresh_anchor_positions,
                arrangement_anchor_status,
            )

            if not positions_refreshed:
                _refresh_anchor_positions(self.scene, update_visuals=True)
            names = tuple(getattr(self.scene, "ArrangementPointObjects", ()) or ())
            objects = tuple(
                obj
                for obj in (document.getObject(str(name)) for name in names)
                if obj is not None
                and getattr(obj, "FittingType", "") == "ArrangementPoint"
            )
            stale_states = {
                "stale",
                "missing target",
                "invalid",
                "wrong target",
                "unconfigured target",
            }
            records = []
            for obj in objects:
                status = arrangement_anchor_status(obj)
                obj.AnchorStatus = status
                stale = status in stale_states
                if stale:
                    obj.Label = "Stale anchor: " + str(getattr(obj, "PointName", obj.Name))
                    obj.ViewObject.ShapeColor = SNAP_STALE_COLOR
                    obj.ViewObject.LineColor = (0.65, 0.10, 0.08)
                else:
                    obj.Label = "Snap target: " + str(getattr(obj, "PointName", obj.Name))
                    obj.ViewObject.ShapeColor = SNAP_TARGET_COLOR
                    obj.ViewObject.LineColor = (0.05, 0.45, 0.72)
                position = (
                    float(obj.X),
                    float(obj.Y),
                    float(obj.Offset),
                )
                records.append((str(obj.Name), position, status))
            self._hide_anchor_feature_objects(objects)
            signature = tuple(records)
            if (
                self._anchor_overlay is not None
                and signature == self._anchor_overlay_signature
            ):
                return

            self._clear_anchor_overlay()
            overlay = _xray_overlay(coin, "ClothInteractiveArrangeAnchorOverlay")
            for _name, position, status in records:
                color = SNAP_STALE_COLOR if status in stale_states else SNAP_TARGET_COLOR
                overlay.addChild(_billboard_marker(coin, position, color))
            self.view.getSceneGraph().addChild(overlay)
            self._anchor_overlay = overlay
            self._anchor_overlay_signature = signature
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self._clear_anchor_overlay()
            self._restore_anchor_feature_visibility()
            self._status("Attachment-point overlay unavailable — {}".format(exc))

    def _queue_snap_indicator(self, point):
        """Defer scene-graph mutation until Coin finishes the active event traversal."""
        self._pending_snap_point = point
        if self._snap_indicator_update_pending:
            return
        self._snap_indicator_update_pending = True
        generation = self._snap_indicator_generation

        def apply_pending():
            if generation != self._snap_indicator_generation:
                return
            self._snap_indicator_update_pending = False
            pending = self._pending_snap_point
            self._pending_snap_point = None
            if self.view is None:
                return
            self._show_snap_indicator(pending)

        self.QtCore.QTimer.singleShot(0, apply_pending)

    def _set_piece_placement(self, piece, base, rotation_z):
        piece.Placement = self.App.Placement(
            self.App.Vector(float(base[0]), float(base[1]), float(base[2])),
            self.App.Rotation(self.App.Vector(0, 0, 1), float(rotation_z)),
        )

    def _begin_transaction(self):
        if self.scene is None or self._transaction_open:
            return
        self.scene.Document.openTransaction("Interactive Cloth Arrange")
        self._transaction_open = True

    def _commit_transaction(self):
        if self._transaction_open:
            self.scene.Document.commitTransaction()
            self._transaction_open = False

    def _abort_transaction(self):
        if self._transaction_open:
            self.scene.Document.abortTransaction()
            self._transaction_open = False

    def activate(self):
        """Install viewport callbacks and enable direct garment dragging."""
        if self.scene is None:
            raise RuntimeError("a fitting scene is required for Interactive Arrange")
        self.view = self.Gui.activeDocument().activeView() if self.Gui.activeDocument() else None
        if self.view is None:
            raise RuntimeError("an active FreeCAD 3D view is required for Interactive Arrange")
        if self._mouse_callback is not None:
            return
        self._refresh_anchor_overlay()
        self._mouse_callback = self.view.addEventCallback("SoMouseButtonEvent", self._mouse_event)
        self._location_callback = self.view.addEventCallback(
            "SoLocation2Event", self._location_event
        )
        self._status(
            "Drag a pattern piece in the 3D view. Blue crosshairs mark arrangement snap targets."
        )

    def deactivate(self):
        """Remove viewport callbacks and cancel any uncommitted drag."""
        if self.drag_piece is not None and self.drag_start_base is not None:
            with contextlib.suppress(AttributeError, RuntimeError, TypeError, ValueError):
                self._set_piece_placement(
                    self.drag_piece,
                    self.drag_start_base,
                    self.drag_start_rotation,
                )
        self.drag_piece = None
        self.snap_point = None
        self._snap_indicator_generation += 1
        self._pending_snap_point = None
        self._snap_indicator_update_pending = False
        self._clear_snap_indicator()
        self._clear_anchor_overlay()
        self._restore_anchor_feature_visibility()
        self._abort_transaction()
        if self.view is not None:
            if self._mouse_callback is not None:
                self.view.removeEventCallback("SoMouseButtonEvent", self._mouse_callback)
            if self._location_callback is not None:
                self.view.removeEventCallback("SoLocation2Event", self._location_callback)
        self._mouse_callback = None
        self._location_callback = None
        self.view = None

    def _mouse_event(self, info):
        position = self._event_position(info)
        if position is None:
            return
        state = str(info.get("State", "")).upper()
        button = str(info.get("Button", "BUTTON1")).upper()
        if button not in {"BUTTON1", "LEFT"}:
            return
        if state == "DOWN":
            piece = self._piece_from_info(info)
            if piece is None:
                return
            cursor = self.view.getPoint(int(position[0]), int(position[1]))
            self.drag_piece = piece
            self.drag_start_screen = position
            self.drag_start_world = cursor
            placement = piece.Placement
            self.drag_start_base = (
                float(placement.Base.x),
                float(placement.Base.y),
                float(placement.Base.z),
            )
            self.drag_start_rotation = float(placement.Rotation.Angle)
            self.snap_point = None
            self._queue_snap_indicator(None)
            self._begin_transaction()
            self.Gui.Selection.clearSelection()
            self.Gui.Selection.addSelection(piece)
            self._status("Dragging {} — release near a blue crosshair to snap.".format(piece.Label))
        elif state == "UP" and self.drag_piece is not None:
            piece = self.drag_piece
            snap = self.snap_point
            try:
                from freecad_cloth.avatar.FittingCommands import position_piece

                placement = piece.Placement
                if snap is not None and self.snap_enabled:
                    position_piece(
                        piece,
                        float(snap.X),
                        float(snap.Y),
                        float(snap.Offset),
                        arrangement_rotation(snap),
                    )
                    self._status(
                        "Snapped {} to {}.".format(
                            piece.Label,
                            getattr(snap, "PointName", "arrangement point"),
                        )
                    )
                else:
                    position_piece(
                        piece,
                        float(placement.Base.x),
                        float(placement.Base.y),
                        float(placement.Base.z),
                        float(placement.Rotation.Angle),
                    )
                    self._status("Placed {}.".format(piece.Label))
            except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self._abort_transaction()
                self.drag_piece = None
                self.snap_point = None
                self._status("Placement blocked — {}".format(exc))
                return
            self._commit_transaction()
            self.drag_piece = None
            self.snap_point = None
            self._queue_snap_indicator(None)

    def _location_event(self, info):
        if self.drag_piece is None or self.drag_start_screen is None:
            return
        position = self._event_position(info)
        if position is None:
            return
        dx = position[0] - self.drag_start_screen[0]
        dy = position[1] - self.drag_start_screen[1]
        if dx * dx + dy * dy < self.DRAG_PIXEL_THRESHOLD**2:
            return
        try:
            cursor = self.view.getPoint(int(position[0]), int(position[1]))
            delta = cursor.sub(self.drag_start_world)
            base = (
                self.drag_start_base[0] + float(delta.x),
                self.drag_start_base[1] + float(delta.y),
                self.drag_start_base[2] + float(delta.z),
            )
            screen_position = coin_position_to_screen(position, self.view.getSize()[1])
            snap = self._nearest_snap_point(screen_position) if self.snap_enabled else None
            self.snap_point = snap
            if snap is not None:
                self._queue_snap_indicator(snap)
                base = (float(snap.X), float(snap.Y), float(snap.Offset))
                rotation = arrangement_rotation(snap)
                self._status(
                    "Snap preview: {} → {}.".format(
                        self.drag_piece.Label,
                        getattr(snap, "PointName", "arrangement point"),
                    )
                )
            else:
                self._queue_snap_indicator(None)
                rotation = self.drag_start_rotation
            self._set_piece_placement(self.drag_piece, base, rotation)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            self.snap_point = None

    def set_snap_enabled(self, enabled):
        """Enable or disable live snapping while the controller is active."""
        self.snap_enabled = bool(enabled)
        self._status(
            "Snap enabled." if self.snap_enabled else "Snap disabled; drag uses the view plane."
        )


class ViewportAnchorPicker:
    """Turn the next viewport face selection into a persistent snap anchor."""

    def __init__(self, panel):
        _App, self.Gui, _QtCore, _QtWidgets = _modules()
        self.panel = panel
        self.armed = False
        self.Gui.Selection.addObserver(self)

    def arm(self):
        """Wait for the user to select a face on the configured target in the viewport."""
        self.armed = True
        self.panel.pick_surface_button.setEnabled(False)
        self.panel.cancel_pick_button.setVisible(True)
        self.panel.status.setText(
            "Pick a face on the configured avatar/target in the 3D view. "
            "The clicked location becomes a persistent snap anchor."
        )

    def cancel(self):
        """Leave surface-pick mode without changing the document."""
        self.armed = False
        self.panel.pick_surface_button.setEnabled(True)
        self.panel.cancel_pick_button.setVisible(False)
        self.panel.status.setText("Surface pick cancelled; the document was not changed.")

    def _finish(self):
        self.armed = False
        self.panel.pick_surface_button.setEnabled(True)
        self.panel.cancel_pick_button.setVisible(False)

    def _target_sources(self):
        """Return the target currently authoritative for this fitting scene."""
        scene = self.panel.scene
        doc = getattr(scene, "Document", None)
        candidate = getattr(scene, "AvatarProxy", None)
        if candidate is None and doc is not None:
            drape_target = doc.getObject("DrapeTarget")
            candidate = getattr(drape_target, "SourceObject", None)
        if candidate is None or not getattr(candidate, "Name", ""):
            return {}
        return {str(candidate.Name): candidate}

    def _world_point(self, object_name, position):
        """Normalize FreeCAD selection callback variants to a world-space Vector."""
        candidates = ()
        if len(position) == 3:
            candidates = (position,)
        elif len(position) == 1:
            value = position[0]
            if all(hasattr(value, name) for name in ("x", "y", "z")):
                coordinates = tuple(getattr(value, name) for name in ("x", "y", "z"))
                candidates = (coordinates,)
            elif isinstance(value, str):
                text = value.strip().strip("()[]")
                candidates = (tuple(part.strip() for part in text.split(",")),)
            else:
                try:
                    coordinates = tuple(value)
                except TypeError:
                    coordinates = ()
                if len(coordinates) >= 3:
                    candidates = (coordinates[:3],)
        for coordinates in candidates:
            try:
                return self.panel.App.Vector(*(float(value) for value in coordinates))
            except (TypeError, ValueError):
                continue
        for selection in self.Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            if str(getattr(obj, "Name", "")) != str(object_name):
                continue
            points = tuple(getattr(selection, "PickedPoints", ()) or ())
            if points:
                picked = points[0]
                try:
                    return self.panel.App.Vector(float(picked.x), float(picked.y), float(picked.z))
                except (AttributeError, TypeError, ValueError):
                    continue
        return None

    def addSelection(self, doc_name, object_name, subelement_name, *position):
        """Consume FreeCAD's selected subelement across supported callback signatures."""
        if not self.armed:
            return
        sources = self._target_sources()
        target = sources.get(str(object_name))
        if target is None:
            self.panel.status.setText(
                "That object is not the configured fitting target. Pick the avatar/target surface."
            )
            return
        picked_sub_element = str(subelement_name or "")
        if not picked_sub_element:
            for selection in self.Gui.Selection.getSelectionEx():
                obj = getattr(selection, "Object", None)
                if str(getattr(obj, "Name", "")) != str(object_name):
                    continue
                names = tuple(getattr(selection, "SubElementNames", ()) or ())
                if names:
                    picked_sub_element = str(names[0])
                    break
        world_point = self._world_point(object_name, position)
        # Mesh::Feature selections may provide a picked world coordinate without a
        # TopoShape-style FaceN subelement name. Keep an explicit surface-kind label
        # so mannequin meshes can use the same viewport workflow as BRep targets.
        mesh = getattr(target, "Mesh", None)
        if not picked_sub_element and mesh is not None:
            picked_sub_element = "MeshSurface"
        if world_point is None or not picked_sub_element:
            self.panel.status.setText(
                "Pick an actual face/triangle on the configured target, not empty viewport space."
            )
            return
        name = str(self.panel.anchor_name.text()).strip()
        if not name:
            name = self.panel._next_anchor_name()
        try:
            from freecad_cloth.avatar.FittingCommands import create_arrangement_anchor

            point = create_arrangement_anchor(
                name,
                target,
                world_point,
                subelement=picked_sub_element,
                wrap_direction=str(self.panel.wrap_direction.currentText()),
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.panel.status.setText("Could not create surface anchor — {}.".format(exc))
            return
        self._finish()
        self.Gui.Selection.clearSelection()
        self.panel.controller._refresh_anchor_overlay()
        self.panel.anchor_name.setText(self.panel._next_anchor_name())
        self.panel._refresh_context()
        self.panel.status.setText(
            "Created surface anchor '{}'. Drag a pattern piece to its marker; target changes "
            "invalidate the anchor, and the anchor does not attach cloth to the surface.".format(
                point.name
            )
        )

    def dispose(self):
        """Disarm picking and unregister the FreeCAD selection observer."""
        self.armed = False
        with contextlib.suppress(AttributeError, RuntimeError):
            self.Gui.Selection.removeObserver(self)


class FittingTaskPanel:
    """Task panel for direct garment placement around a persistent avatar target."""

    def __init__(self, scene=None):
        App, Gui, QtCore, QtWidgets = _modules()
        self.App, self.Gui, self.QtCore, self.scene = App, Gui, QtCore, scene
        if self.scene is None:
            from freecad_cloth.avatar.FittingCommands import create_fitting_scene

            self.scene = create_fitting_scene()
        try:
            from freecad_cloth.avatar.FittingCommands import _sync_visuals

            _sync_visuals(self.scene)
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
            pass

        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothInteractiveArrangeTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        context = QtWidgets.QGroupBox("Fitting")
        context_layout = QtWidgets.QVBoxLayout(context)
        self.context = QtWidgets.QLabel()
        self.context.setWordWrap(True)
        context_layout.addWidget(self.context)
        root.addWidget(context)

        actions = QtWidgets.QGroupBox("Arrange")
        action_layout = QtWidgets.QVBoxLayout(actions)
        self.instruction = QtWidgets.QLabel(
            "Drag a pattern piece. Blue crosshairs mark where its placement origin will snap; release to commit."
        )
        self.instruction.setWordWrap(True)
        action_layout.addWidget(self.instruction)
        self.snap = QtWidgets.QCheckBox("Snap to arrangement points")
        self.snap.setChecked(True)
        self.snap.setToolTip(
            "When a dragged piece is close to an arrangement point, preview and apply its saved orientation."
        )
        action_layout.addWidget(self.snap)
        buttons = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton("Reset arrangement")
        self.fit_button = QtWidgets.QPushButton("Fit view")
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.fit_button)
        action_layout.addLayout(buttons)
        root.addWidget(actions)

        anchors = QtWidgets.QGroupBox("Surface snap target")
        anchor_layout = QtWidgets.QVBoxLayout(anchors)
        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel("Name"))
        self.anchor_name = QtWidgets.QLineEdit()
        self.anchor_name.setText(self._next_anchor_name())
        self.anchor_name.setToolTip("Name stored with the picked snap target.")
        name_row.addWidget(self.anchor_name)
        anchor_layout.addLayout(name_row)
        direction_row = QtWidgets.QHBoxLayout()
        direction_row.addWidget(QtWidgets.QLabel("Wrap direction"))
        self.wrap_direction = QtWidgets.QComboBox()
        for direction in ("front", "back", "left", "right"):
            self.wrap_direction.addItem(direction)
        self.wrap_direction.setToolTip(
            "Orientation applied when a pattern piece snaps to this anchor."
        )
        direction_row.addWidget(self.wrap_direction)
        anchor_layout.addLayout(direction_row)
        pick_buttons = QtWidgets.QHBoxLayout()
        self.pick_surface_button = QtWidgets.QPushButton("Pick surface in viewport")
        self.cancel_pick_button = QtWidgets.QPushButton("Cancel pick")
        self.cancel_pick_button.setVisible(False)
        pick_buttons.addWidget(self.pick_surface_button)
        pick_buttons.addWidget(self.cancel_pick_button)
        anchor_layout.addLayout(pick_buttons)
        self.anchor_hint = QtWidgets.QLabel(
            "Choose a name, start picking, then click a face on the configured avatar/target. "
            "The point controls piece placement; it does not pin cloth to the surface."
        )
        self.anchor_hint.setWordWrap(True)
        anchor_layout.addWidget(self.anchor_hint)
        root.addWidget(anchors)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)

        self.controller = DirectArrangeController(
            self.scene,
            status_callback=self.status.setText,
            snap_enabled=True,
        )
        self.anchor_picker = ViewportAnchorPicker(self)
        self.pick_surface_button.clicked.connect(self.start_anchor_pick)
        self.cancel_pick_button.clicked.connect(self.anchor_picker.cancel)
        self.snap.toggled.connect(self.controller.set_snap_enabled)
        self.reset_button.clicked.connect(self.reset_arrangement)
        self.fit_button.clicked.connect(self._fit_view)
        self._refresh_context()
        self.controller.activate()

    def _next_anchor_name(self):
        """Return a predictable name not already used by a saved snap point."""
        from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

        existing = {
            point.name
            for point in (
                ArrangementPoint.from_string(value)
                for value in tuple(getattr(self.scene, "ArrangementPoints", ()) or ())
            )
        }
        index = 1
        while "SurfaceAnchor{}".format(index) in existing:
            index += 1
        return "SurfaceAnchor{}".format(index)

    def start_anchor_pick(self):
        """Arm one viewport selection to create a surface-aware arrangement point."""
        self.anchor_picker.arm()

    def _refresh_context(self):
        from freecad_cloth.avatar.FittingCommands import arrangement_anchor_status

        pieces = tuple(getattr(self.scene, "PatternPieces", ()) or ())
        names = tuple(getattr(self.scene, "ArrangementPointObjects", ()) or ())
        doc = getattr(self.scene, "Document", None)
        point_objects = (
            tuple(obj for obj in (doc.getObject(str(name)) for name in names) if obj is not None)
            if doc is not None
            else ()
        )
        target = getattr(self.scene, "AvatarProxy", None)
        if target is None and doc is not None:
            drape_target = doc.getObject("DrapeTarget")
            target = getattr(drape_target, "SourceObject", None)
        target_name = getattr(target, "Label", "No target")
        stale = sum(
            arrangement_anchor_status(point)
            in {"stale", "missing target", "invalid", "wrong target", "unconfigured target"}
            for point in point_objects
        )
        suffix = " | {} stale anchor(s) excluded".format(stale) if stale else ""
        self.context.setText(
            "{} piece(s) | {} snap point(s) | Target: {}{}".format(
                len(pieces), len(point_objects), target_name, suffix
            )
        )

    def reset_arrangement(self):
        """Restore saved home placements without changing fitting metadata."""
        try:
            from freecad_cloth.avatar.FittingCommands import reset_arrangement

            reset_arrangement()
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.status.setText("Reset unavailable — {}".format(exc))
            return
        self._refresh_context()
        self._fit_view()
        self.status.setText("Arrangement reset to the saved starting positions.")

    def _fit_view(self):
        """Fit the active FreeCAD view to the fitting scene."""
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        """Commit the current interaction and close the task panel."""
        self.anchor_picker.dispose()
        self.controller.deactivate()
        return True

    def reject(self):
        """Cancel an active drag and close the task panel."""
        self.anchor_picker.dispose()
        self.controller.deactivate()
        return True

    def getStandardButtons(self):
        _, _, _, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_fitting_task(scene=None):
    """Open the direct-manipulation fitting task panel."""
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = FittingTaskPanel(scene)
    Gui.Control.showDialog(panel)
    return panel

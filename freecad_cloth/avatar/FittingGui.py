"""Direct-manipulation fitting UI for the Cloth Sewing workbench.

The fitting scene remains authoritative; viewport movement is an interactive
frontend that commits final placements through FittingCommands. Numeric
placement values are deliberately absent from the normal workflow and remain
available through FreeCAD's property editor for precision work.
"""

import contextlib


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


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

    def _status(self, message):
        self.status_callback(str(message))

    def _points(self):
        if self.scene is None:
            return ()
        result = []
        document = getattr(self.scene, "Document", None)
        if document is None:
            return ()
        for name in tuple(getattr(self.scene, "ArrangementPointObjects", ()) or ()):
            obj = document.getObject(str(name))
            if obj is not None and getattr(obj, "FittingType", "") == "ArrangementPoint":
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
            separator = coin.SoSeparator()
            transform = coin.SoTransform()
            transform.translation.setValue(
                coin.SbVec3f(float(point.X), float(point.Y), float(point.Offset))
            )
            color = coin.SoBaseColor()
            color.rgb = (0.15, 0.75, 1.0)
            sphere = coin.SoSphere()
            sphere.radius = 8.0
            separator.addChild(transform)
            separator.addChild(color)
            separator.addChild(sphere)
            self.view.getSceneGraph().addChild(separator)
            self._snap_indicator = separator
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
            self._snap_indicator = None

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
        self._mouse_callback = self.view.addEventCallback("SoMouseButtonEvent", self._mouse_event)
        self._location_callback = self.view.addEventCallback("SoLocation2Event", self._location_event)
        self._status(
            "Drag a pattern piece in the 3D view. Blue arrangement points are snap targets."
        )

    def deactivate(self):
        """Remove viewport callbacks and cancel any uncommitted drag."""
        if self.drag_piece is not None and self.drag_start_base is not None:
            try:
                self._set_piece_placement(
                    self.drag_piece,
                    self.drag_start_base,
                    self.drag_start_rotation,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        self.drag_piece = None
        self.snap_point = None
        self._clear_snap_indicator()
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
            self._clear_snap_indicator()
            self._begin_transaction()
            self.Gui.Selection.clearSelection()
            self.Gui.Selection.addSelection(piece)
            self._status(
                "Dragging {} — release near a blue point to snap.".format(piece.Label)
            )
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
            self._clear_snap_indicator()

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
            snap = self._nearest_snap_point(position) if self.snap_enabled else None
            self.snap_point = snap
            if snap is not None:
                self._show_snap_indicator(snap)
                base = (float(snap.X), float(snap.Y), float(snap.Offset))
                rotation = arrangement_rotation(snap)
                self._status(
                    "Snap preview: {} → {}.".format(
                        self.drag_piece.Label,
                        getattr(snap, "PointName", "arrangement point"),
                    )
                )
            else:
                self._clear_snap_indicator()
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
            "Drag a pattern piece in the 3D view. Hover near a blue arrangement point to preview a snap."
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

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)

        self.controller = DirectArrangeController(
            self.scene,
            status_callback=self.status.setText,
            snap_enabled=True,
        )
        self.snap.toggled.connect(self.controller.set_snap_enabled)
        self.reset_button.clicked.connect(self.reset_arrangement)
        self.fit_button.clicked.connect(self._fit_view)
        self._refresh_context()
        self.controller.activate()

    def _refresh_context(self):
        pieces = tuple(getattr(self.scene, "PatternPieces", ()) or ())
        points = tuple(getattr(self.scene, "ArrangementPointObjects", ()) or ())
        target = getattr(self.scene, "AvatarProxy", None) or getattr(
            self.scene, "DrapeTarget", None
        )
        target_name = getattr(target, "Label", "No target")
        self.context.setText(
            "{} piece(s) | {} snap point(s) | Target: {}".format(
                len(pieces),
                len(points),
                target_name,
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
        self.controller.deactivate()
        return True

    def reject(self):
        """Cancel an active drag and close the task panel."""
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

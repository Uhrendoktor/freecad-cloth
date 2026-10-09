"""Transient staged creation session for semantic sewing objects.

Preview creates the normal FreeCAD seam/network objects inside the same
document transaction used by other sewing task panels. Commit closes that
transaction; Cancel aborts it. The session itself is transient UI state only.
"""


import re


def viewport_edge_candidate(document, hit_info):
    """Resolve a FreeCAD viewport hit to an authored PatternPiece edge."""
    if not isinstance(hit_info, dict):
        return None
    component = str(hit_info.get("Component", "")).strip()
    match = re.fullmatch(r"Edge\s*(\d+)", component, flags=re.IGNORECASE)
    if match is None or int(match.group(1)) < 1:
        return None
    object_key = str(hit_info.get("Object", hit_info.get("ObjectName", ""))).strip()
    if not object_key:
        return None
    target = None
    for candidate in getattr(document, "Objects", ()):
        name = str(getattr(candidate, "Name", ""))
        label = str(getattr(candidate, "Label", ""))
        if object_key in {name, label} or object_key.startswith(name + " ("):
            target = candidate
            break
    if target is None or str(getattr(target, "PatternType", "")) != "PatternPiece":
        return None
    return target, "Edge" + match.group(1)


def _close_active_task_dialog():
    import FreeCADGui as Gui

    if Gui.activeDocument() and Gui.Control.activeDialog():
        Gui.Control.closeDialog()


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class SewingCreationSession:
    """Stage one sewing creation inside one FreeCAD document transaction."""

    def __init__(self, doc, gui, transaction_name, builder):
        self.doc = doc
        self.gui = gui
        self.transaction_name = str(transaction_name)
        self.builder = builder
        self.created = ()
        self.previewed = False
        self.committed = False
        self._transaction_active = False
        self._original_selection = tuple(gui.Selection.getSelection()) if gui is not None else ()
        self._begin_transaction()

    def _begin_transaction(self):
        opener = getattr(self.doc, "openTransaction", None) if self.doc is not None else None
        if callable(opener):
            opener(self.transaction_name)
            self._transaction_active = True

    def _commit_transaction(self):
        if not self._transaction_active:
            return
        committer = getattr(self.doc, "commitTransaction", None) if self.doc is not None else None
        if callable(committer):
            committer()
        self._transaction_active = False

    def _abort_transaction(self):
        if not self._transaction_active:
            return False
        aborter = getattr(self.doc, "abortTransaction", None) if self.doc is not None else None
        if callable(aborter):
            aborter()
            self._transaction_active = False
            return True
        self._transaction_active = False
        return False

    def _reset_preview(self):
        self._abort_transaction()
        self.created = ()
        self.previewed = False
        self._begin_transaction()

    @staticmethod
    def _new_objects(before_names, doc):
        return tuple(
            obj
            for obj in getattr(doc, "Objects", ())
            if str(getattr(obj, "Name", "")) not in before_names
        )

    def _validate_preview(self):
        if not self.created:
            raise ValueError("Preview did not create a sewing object")
        invalid = []
        for obj in self.created:
            sewing_type = str(getattr(obj, "SewingType", ""))
            seam_id = str(getattr(obj, "SeamId", ""))
            if sewing_type in {"SewingNetwork", "SewingOperation"} or seam_id:
                status = str(getattr(obj, "Status", "Valid"))
                if status != "Valid":
                    identity = (
                        seam_id
                        or str(getattr(obj, "RelationshipId", ""))
                        or str(getattr(obj, "Name", "<unnamed>"))
                    )
                    invalid.append(f"{identity}: {status}")
        if invalid:
            raise ValueError("Preview validation failed: " + "; ".join(invalid))

    def _select_created(self):
        if self.gui is None:
            return
        selection = getattr(self.gui, "Selection", None)
        if selection is None:
            return
        clearer = getattr(selection, "clearSelection", None)
        adder = getattr(selection, "addSelection", None)
        if callable(clearer):
            clearer()
        if callable(adder):
            for obj in self.created:
                adder(obj)

    def _restore_selection(self):
        if self.gui is None:
            return
        selection = getattr(self.gui, "Selection", None)
        if selection is None:
            return
        clearer = getattr(selection, "clearSelection", None)
        adder = getattr(selection, "addSelection", None)
        if callable(clearer):
            clearer()
        if callable(adder):
            for obj in self._original_selection:
                try:
                    adder(obj)
                except (RuntimeError, ValueError):
                    continue

    def preview(self):
        """Create and validate the normal persisted objects, still uncommitted."""
        if self.committed:
            raise ValueError("sewing creation has already been committed")
        if self.previewed:
            self._reset_preview()
        before_names = {str(getattr(obj, "Name", "")) for obj in getattr(self.doc, "Objects", ())}
        try:
            self.builder()
            self.doc.recompute()
            self.created = self._new_objects(before_names, self.doc)
            self._validate_preview()
        except Exception:
            self._abort_transaction()
            self.created = ()
            self.previewed = False
            self._begin_transaction()
            self._restore_selection()
            raise
        self.previewed = True
        self._select_created()
        return self.created

    def commit(self):
        """Validate the staged objects once, then commit the document transaction."""
        if self.committed:
            raise ValueError("sewing creation has already been committed")
        if not self.previewed:
            self.preview()
        self.doc.recompute()
        self._validate_preview()
        self._commit_transaction()
        self.previewed = False
        self.committed = True
        self._select_created()
        return self.created

    def cancel(self):
        """Abort the creation transaction, restoring the document and prior selection."""
        if self.committed:
            return True
        self._abort_transaction()
        self.created = ()
        self.previewed = False
        if self.doc is not None:
            self.doc.recompute()
        self._restore_selection()
        return True


class SewingCreationTaskPanel:
    """Small Preview/Commit/Cancel task panel for one staged sewing creation."""

    _TRANSACTION_NAMES = {
        "seam": "Create Seam",
        "mn": "Create M:N Sewing",
        "free": "Create Free Sewing",
    }

    def __init__(self, kind):
        App, Gui, QtWidgets = _modules()
        if App.ActiveDocument is None:
            raise ValueError("open a document before creating sewing")
        if kind not in self._TRANSACTION_NAMES:
            raise ValueError(f"unsupported staged sewing creation: {kind}")
        self.App, self.Gui = App, Gui
        self.kind = kind
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Sewing — staged creation")
        layout = QtWidgets.QVBoxLayout(self.form)
        self.info = QtWidgets.QLabel(
            "Select authored PatternPiece edges, or use viewport picking below. "
            "Preview validates and stages the normal sewing objects; Commit persists them."
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.selection = QtWidgets.QLabel()
        self.selection.setWordWrap(True)
        layout.addWidget(self.selection)

        self.feedback = QtWidgets.QLabel()
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("ClothSewingCreationFeedback")
        layout.addWidget(self.feedback)

        self.viewport_pick_button = QtWidgets.QPushButton("Pick edges in viewport")
        self.viewport_pick_button.clicked.connect(self.toggle_viewport_picking)
        layout.addWidget(self.viewport_pick_button)

        buttons = QtWidgets.QHBoxLayout()
        self.preview_button = QtWidgets.QPushButton("Preview")
        self.commit_button = QtWidgets.QPushButton("Commit")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.preview_button.clicked.connect(self.preview)
        self.commit_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.commit_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.session = SewingCreationSession(
            App.ActiveDocument,
            Gui,
            self._TRANSACTION_NAMES[kind],
            self._builder,
        )
        self._closing = False
        self._viewport_picking = False
        self._viewport_view = None
        self._viewport_callback = None
        self._viewport_picks = []
        self._refresh_selection()
        self.preview()

    def _builder(self):
        if self.kind == "seam":
            from freecad_cloth.sewing.SewingCommands import create_seam_from_selection

            return create_seam_from_selection()
        if self.kind == "mn":
            from freecad_cloth.sewing.SewingCommands import create_mn_sewing_from_selection

            return create_mn_sewing_from_selection()
        from freecad_cloth.sewing.SewingNetworkCommands import create_free_sewing_from_selection

        return create_free_sewing_from_selection(open_editor=False)

    def _refresh_selection(self):
        try:
            from freecad_cloth.sewing.SewingCommands import _collect_selected_pattern_edges

            count = len(_collect_selected_pattern_edges())
        except (ImportError, ValueError):
            count = 0
        if self._viewport_picks:
            picked = " → ".join(
                "{} / {}".format(getattr(obj, "Label", getattr(obj, "Name", "PatternPiece")), edge)
                for obj, edge in self._viewport_picks
            )
            self.selection.setText("Viewport picks (%d): %s" % (len(self._viewport_picks), picked))
        else:
            self.selection.setText(
                "Selected semantic pattern edges: %d. Preview applies the existing "
                "edge-count and two-piece validation." % count
            )

    def toggle_viewport_picking(self):
        if self._viewport_picking:
            self._stop_viewport_picking()
            self.feedback.setText("Viewport picking paused. Press Preview to review the selected edges.")
            self.feedback.setStyleSheet("")
            self.commit_button.setEnabled(False)
            return
        self._start_viewport_picking()

    def _start_viewport_picking(self):
        active = self.Gui.activeDocument()
        if active is None or active.activeView() is None:
            self._show_error(RuntimeError("an active 3D view is required for viewport edge picking"))
            return
        if self.session.previewed:
            self.session._reset_preview()
        self._viewport_picks = []
        self.Gui.Selection.clearSelection()
        self._viewport_view = active.activeView()
        try:
            self._viewport_callback = self._viewport_view.addEventCallback(
                "SoMouseButtonEvent", self._viewport_mouse_event
            )
        except (AttributeError, RuntimeError, TypeError) as exc:
            self._viewport_view = None
            self._viewport_callback = None
            self._show_error(RuntimeError("viewport edge picking could not start: {}".format(exc)))
            return
        self._viewport_picking = True
        self.viewport_pick_button.setText("Stop viewport picking")
        self.commit_button.setEnabled(False)
        self._refresh_selection()
        if self.kind == "seam":
            message = (
                "Click the first PatternPiece edge in the viewport. Then click its counterpart "
                "on a different piece; a colored A/B preview will appear automatically."
            )
        else:
            message = (
                "Click the relevant PatternPiece edges in the viewport, stop picking, then press "
                "Preview to validate the relationship."
            )
        self.feedback.setText(message)
        self.feedback.setStyleSheet("")
        self.commit_button.setEnabled(False)

    def _stop_viewport_picking(self):
        if self._viewport_view is not None and self._viewport_callback is not None:
            try:
                self._viewport_view.removeEventCallback(
                    "SoMouseButtonEvent", self._viewport_callback
                )
            except (AttributeError, RuntimeError, TypeError):
                pass
        self._viewport_view = None
        self._viewport_callback = None
        self._viewport_picking = False
        if getattr(self, "viewport_pick_button", None) is not None:
            self.viewport_pick_button.setText("Pick edges in viewport")

    def _viewport_mouse_event(self, event):
        if not self._viewport_picking or self._closing:
            return
        if str(event.get("State", "")).upper() != "DOWN":
            return
        if str(event.get("Button", "BUTTON1")).upper() not in {"BUTTON1", "LEFT"}:
            return
        position = event.get("Position", (0, 0))
        try:
            hit = self._viewport_view.getObjectInfo(int(position[0]), int(position[1]))
        except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
            hit = None
        candidate = viewport_edge_candidate(self.App.ActiveDocument, hit)
        if candidate is None:
            self.feedback.setText("Pick an outline edge on a PatternPiece, not a face or sewing overlay.")
            self.feedback.setStyleSheet("")
            return
        obj, component = candidate
        if any(previous is obj and edge == component for previous, edge in self._viewport_picks):
            return
        if self.kind == "seam" and self._viewport_picks and self._viewport_picks[0][0] is obj:
            self.feedback.setText("Choose the counterpart edge on a different PatternPiece.")
            self.feedback.setStyleSheet("")
            return
        self._viewport_picks.append((obj, component))
        self.Gui.Selection.clearSelection()
        for picked_obj, picked_edge in self._viewport_picks:
            self.Gui.Selection.addSelection(picked_obj, picked_edge)
        self._refresh_selection()
        if self.kind == "seam" and len(self._viewport_picks) == 1:
            self.feedback.setText(
                "Side A: {} / {}. Click the matching edge on another PatternPiece.".format(
                    getattr(obj, "Label", obj.Name), component
                )
            )
            self.feedback.setStyleSheet("")
            return
        if self.kind == "seam" and len(self._viewport_picks) == 2:
            self._stop_viewport_picking()
            if not self.preview():
                self._viewport_picks = []
                self._refresh_selection()
            else:
                self.feedback.setText(
                    "Seam preview shown. Review the matching color and A/B labels, then Commit or Cancel."
                )

    def _show_error(self, exc):

    def _show_error(self, exc):
        self.feedback.setText(
            f"Preview rejected: {str(exc)}. Adjust the selection, then press Preview again."
        )
        self.feedback.setStyleSheet("font-weight: bold;")
        self.commit_button.setEnabled(False)

    def _show_status(self, text):
        self.feedback.setText(text)
        self.feedback.setStyleSheet("")
        self.commit_button.setEnabled(True)

    def preview(self):
        self._stop_viewport_picking()
        self._refresh_selection()
        try:
            self.session.preview()
        except (ImportError, RuntimeError, ValueError, TypeError) as exc:
            self._show_error(exc)
            return False
        try:
            from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

            refresh_seam_overlay(self.App.ActiveDocument)
        except (ImportError, RuntimeError, TypeError, ValueError):
            pass
        self._show_status(
            "Preview valid: %d document object(s) staged in one undo transaction. "
            "Check the matching colored A/B labels, then Commit or Cancel." % len(self.session.created)
        )
        return True

    def _schedule_close_dialog(self):
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore
        timer = QtCore.QTimer(self.form)
        timer.setSingleShot(True)
        timer.timeout.connect(_close_active_task_dialog)
        self._close_timer = timer
        timer.start(0)

    def accept(self):
        if self._closing:
            return True
        self._stop_viewport_picking()
        try:
            self.session.commit()
        except (ImportError, RuntimeError, ValueError, TypeError) as exc:
            self._show_error(exc)
            return False
        self._closing = True
        self._show_status("Committed sewing creation.")
        self.commit_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self._schedule_close_dialog()
        return True

    def reject(self):
        if self._closing:
            return True
        self._stop_viewport_picking()
        self.session.cancel()
        self._closing = True
        self._show_status("Cancelled. No seam or sewing-network object was persisted.")
        self._schedule_close_dialog()
        return True

    def getStandardButtons(self):
        return 0


def show_sewing_creation_task(kind):
    _App, Gui, _QtWidgets = _modules()
    panel = SewingCreationTaskPanel(kind)
    Gui.Control.showDialog(panel)
    if hasattr(panel.form, "isVisible") and not panel.form.isVisible():
        panel.form.show()
    return panel

"""Transient staged creation session for semantic sewing objects.

Preview creates the normal FreeCAD seam/network objects inside the same
document transaction used by other sewing task panels. Commit closes that
transaction; Cancel aborts it. The session itself is transient UI state only.
"""

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
            obj for obj in getattr(doc, "Objects", ())
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
                    identity = seam_id or str(getattr(obj, "RelationshipId", "")) or str(getattr(obj, "Name", "<unnamed>"))
                    invalid.append("%s: %s" % (identity, status))
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
            raise ValueError("unsupported staged sewing creation: %s" % kind)
        self.App, self.Gui = App, Gui
        self.kind = kind
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Sewing — staged creation")
        layout = QtWidgets.QVBoxLayout(self.form)
        self.info = QtWidgets.QLabel(
            "Select semantic PatternPiece edges, Preview to validate and stage the "
            "normal sewing objects, then Commit once or Cancel to discard them."
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
        self.selection.setText(
            "Selected semantic pattern edges: %d. Preview applies the existing "
            "edge-count and two-piece validation." % count
        )

    def _show_error(self, exc):
        self.feedback.setText(
            "Preview rejected: %s. Adjust the selection, then press Preview again."
            % str(exc)
        )
        self.feedback.setStyleSheet("font-weight: bold;")
        self.commit_button.setEnabled(False)

    def _show_status(self, text):
        self.feedback.setText(text)
        self.feedback.setStyleSheet("")
        self.commit_button.setEnabled(True)

    def preview(self):
        self._refresh_selection()
        try:
            self.session.preview()
        except (ImportError, RuntimeError, ValueError, TypeError) as exc:
            self._show_error(exc)
            return False
        self._show_status(
            "Preview valid: %d document object(s) staged in one undo transaction. "
            "Commit to persist them or Cancel to remove the preview." % len(self.session.created)
        )
        return True

    def _schedule_close_dialog(self):
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(_close_active_task_dialog)
        self._close_timer = timer
        timer.start(0)

    def accept(self):
        try:
            self.session.commit()
        except (ImportError, RuntimeError, ValueError, TypeError) as exc:
            self._show_error(exc)
            return False
        self._show_status("Committed sewing creation.")
        self.commit_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self._schedule_close_dialog()
        return True

    def reject(self):
        self.session.cancel()
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

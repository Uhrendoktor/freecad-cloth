"""FreeCAD task panel for editing sewing operations.

The task panel edits document properties transactionally and rejects stale seam
references after recompute instead of silently accepting invalid state.
"""

def _gui_modules():
    import FreeCAD as App, FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


def validate_seam_for_accept(seam):
    status = str(getattr(seam, "Status", "Valid")) if seam is not None else "Missing seam"
    if status != "Valid":
        seam_id = str(getattr(seam, "SeamId", "")) or "<unnamed>"
        raise ValueError("cannot accept sewing operation with invalid seam reference %s: %s" % (seam_id, status))
    return True


class SewingTaskPanel:
    _TRANSACTION_NAME = "Edit Sewing Operation"

    def __init__(self, obj):
        App, Gui, QtWidgets = _gui_modules()
        self.App, self.Gui, self.obj = App, Gui, obj
        self.seam = getattr(obj, "Seam", None)
        self._transaction_active = False
        self._original = {"Tolerance": float(obj.Tolerance), "Stitches": int(obj.Stitches)}
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(0, 1000)
        self.tolerance.setDecimals(2)
        self.tolerance.setSuffix(" mm")
        self.tolerance.setValue(self._original["Tolerance"])
        self.stitches = QtWidgets.QSpinBox()
        self.stitches.setRange(2, 10000)
        self.stitches.setValue(max(2, self._original["Stitches"]))
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.lengths = QtWidgets.QLabel()
        self.lengths.setWordWrap(True)
        layout.addRow("Validation tolerance", self.tolerance)
        layout.addRow("Stitch samples", self.stitches)
        layout.addRow("Status", self.status)
        layout.addRow("Seam lengths", self.lengths)
        self._begin_transaction()
        self._refresh()

    def _begin_transaction(self):
        doc = self.App.ActiveDocument
        opener = getattr(doc, "openTransaction", None) if doc is not None else None
        if callable(opener):
            opener(self._TRANSACTION_NAME)
            self._transaction_active = True

    def _commit_transaction(self):
        if not self._transaction_active:
            return
        doc = self.App.ActiveDocument
        committer = getattr(doc, "commitTransaction", None) if doc is not None else None
        if callable(committer):
            committer()
        self._transaction_active = False

    def _abort_transaction(self):
        if not self._transaction_active:
            return False
        doc = self.App.ActiveDocument
        aborter = getattr(doc, "abortTransaction", None) if doc is not None else None
        if callable(aborter):
            aborter()
            self._transaction_active = False
            return True
        self._transaction_active = False
        return False

    def _refresh(self):
        self.status.setText(str(self.obj.Status))
        self.lengths.setText("%.2f / %.2f mm (Δ %.2f)" % (float(self.obj.LengthA), float(self.obj.LengthB), float(self.obj.LengthDifference)))

    def update(self):
        self._refresh()

    def accept(self):
        validate_seam_for_accept(self.seam)
        self.obj.Tolerance = self.tolerance.value()
        self.obj.Stitches = self.stitches.value()
        self.App.ActiveDocument.recompute()
        validate_seam_for_accept(self.seam)
        if str(getattr(self.obj, "Status", "")) != "Valid":
            raise ValueError("cannot accept sewing operation: %s" % self.obj.Status)
        self._commit_transaction()
        self._refresh()
        return True

    def reject(self):
        if not self._abort_transaction():
            self.obj.Tolerance = self._original["Tolerance"]
            self.obj.Stitches = self._original["Stitches"]
        self.App.ActiveDocument.recompute()
        self._refresh()
        return True

    def getStandardButtons(self):
        _App, _Gui, QtWidgets = _gui_modules()
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))


def show_sewing_task(obj):
    _App, Gui, _QtWidgets = _gui_modules()
    panel = SewingTaskPanel(obj)
    Gui.Control.showDialog(panel)
    return panel

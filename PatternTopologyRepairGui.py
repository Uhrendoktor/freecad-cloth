"""FreeCAD task panel for explicit semantic-edge topology repair."""


def _gui_modules():
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return Gui, QtWidgets


class PatternTopologyRepairTaskPanel:
    """Show invalid seam sides and require an explicit current-edge mapping."""

    def __init__(self, doc):
        Gui, QtWidgets = _gui_modules()
        from PatternTopologyRepair import current_edge_candidates, invalid_seam_sides

        self.Gui = Gui
        self.doc = doc
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — Repair topology")
        outer = QtWidgets.QVBoxLayout(self.form)
        outer.addWidget(QtWidgets.QLabel(
            "Sketch topology changed. Select the intended current edge for each invalid seam side. "
            "Nothing is remapped automatically."
        ))

        self.rows = []
        grid = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel("Seam"), 0, 0)
        grid.addWidget(QtWidgets.QLabel("Side"), 0, 1)
        grid.addWidget(QtWidgets.QLabel("Reason"), 0, 2)
        grid.addWidget(QtWidgets.QLabel("Current edge"), 0, 3)

        for row, (seam, side, reason) in enumerate(invalid_seam_sides(doc), 1):
            grid.addWidget(QtWidgets.QLabel(str(getattr(seam, "Label", seam.Name))), row, 0)
            grid.addWidget(QtWidgets.QLabel(side), row, 1)
            grid.addWidget(QtWidgets.QLabel(reason), row, 2)
            combo = QtWidgets.QComboBox()
            combo.addItem("Leave unresolved", "")
            for record in current_edge_candidates(seam, side):
                combo.addItem(str(record["id"]), str(record["id"]))
            grid.addWidget(combo, row, 3)
            self.rows.append((seam, side, combo))

        outer.addLayout(grid)
        self.status = QtWidgets.QLabel(
            "%d invalid seam side(s) require an explicit mapping." % len(self.rows)
        )
        outer.addWidget(self.status)

    def accept(self):
        from PatternTopologyRepair import apply_repair_plan
        repairs = [
            (seam, side, combo.currentData())
            for seam, side, combo in self.rows
            if combo.currentData()
        ]
        if not repairs:
            self.status.setText("Select at least one replacement edge before applying repair.")
            return False
        try:
            plan = apply_repair_plan(self.doc, repairs)
        except Exception as exc:
            self.status.setText("Repair failed: %s" % exc)
            return False
        self.status.setText("Repaired %d seam side(s)." % len(plan))
        self.Gui.Control.closeDialog()
        return True

    def reject(self):
        self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        # FreeCAD task panels use standard OK/Cancel button flags.
        return 0x00000400 | 0x00800000


def show_topology_repair_task(doc):
    Gui, _QtWidgets = _gui_modules()
    panel = PatternTopologyRepairTaskPanel(doc)
    Gui.Control.showDialog(panel)
    return panel

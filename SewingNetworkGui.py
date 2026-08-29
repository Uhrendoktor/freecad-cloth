"""FreeCAD task panel for editing semantic sewing-network ranges.

The panel exposes the persisted M:N relationship directly and refuses to
silently edit a network whose canonical seam references are invalid.
"""


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


def network_reference_errors(network):
    """Return ``(seam_id, status)`` for invalid canonical network members."""
    errors = []
    for seam in tuple(getattr(network, "Seams", ()) or ()):
        status = str(getattr(seam, "Status", "Valid"))
        if status != "Valid":
            errors.append((str(getattr(seam, "SeamId", "")) or "<unnamed>", status))
    return tuple(errors)


def validate_network_for_edit(network):
    """Raise a clear error when a persisted network contains invalid seams."""
    errors = network_reference_errors(network)
    if errors:
        details = ", ".join("%s: %s" % item for item in errors)
        raise ValueError("cannot edit sewing network with invalid seam references: " + details)
    return True


class SewingNetworkTaskPanel:
    """Native FreeCAD editor for canonical seam ranges in a sewing network."""

    def __init__(self, network):
        App, Gui, QtCore, QtWidgets = _modules()
        self.App, self.Gui, self.QtCore = App, Gui, QtCore
        self.network = network
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.form)
        self.info = QtWidgets.QLabel(
            "Relationship %s — edit normalized edge ranges (0..1). Ranges are local to each referenced edge."
            % str(getattr(network, "RelationshipId", ""))
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        controls = QtWidgets.QFormLayout()
        self.alignment = QtWidgets.QComboBox()
        self.alignment.addItems(["endpoints", "uniform"])
        alignments = {str(getattr(seam, "Alignment", "endpoints")) for seam in tuple(getattr(network, "Seams", ()) or ())}
        current_alignment = next(iter(alignments), "uniform")
        index = self.alignment.findText(current_alignment)
        self.alignment.setCurrentIndex(max(0, index))
        controls.addRow("Alignment", self.alignment)

        self.reversed_b = QtWidgets.QCheckBox("Reverse B correspondence")
        seam_values = tuple(getattr(network, "Seams", ()) or ())
        self.reversed_b.setChecked(bool(seam_values and all(bool(getattr(seam, "ReversedB", False)) for seam in seam_values)))
        controls.addRow("Orientation", self.reversed_b)
        layout.addLayout(controls)

        errors = network_reference_errors(network)
        self.warning = QtWidgets.QLabel()
        self.warning.setWordWrap(True)
        self.warning.setObjectName("ClothSewingNetworkReferenceWarning")
        self.warning.setText(
            "Invalid seam references: " + "; ".join("%s (%s)" % item for item in errors)
            if errors else ""
        )
        layout.addWidget(self.warning)

        columns = ("A piece", "A edge", "A start", "A end", "B piece", "B edge", "B start", "B end", "Direction", "Status")
        self.table = QtWidgets.QTableWidget(len(seam_values), len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setObjectName("ClothSewingNetworkRangeTable")
        self._seams = seam_values
        for row, seam in enumerate(seam_values):
            values = (
                str(getattr(seam, "PieceA", "")), str(getattr(seam, "EdgeA", "")),
                float(getattr(seam, "StartA", 0.0)), float(getattr(seam, "EndA", 1.0)),
                str(getattr(seam, "PieceB", "")), str(getattr(seam, "EdgeB", "")),
                float(getattr(seam, "StartB", 0.0)), float(getattr(seam, "EndB", 1.0)),
                "reversed" if bool(getattr(seam, "ReversedB", False)) else "forward",
                str(getattr(seam, "Status", getattr(network, "Status", ""))),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if column not in (2, 3, 6, 7):
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(row, column, item)
        layout.addWidget(self.table)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self._refresh_status()

    def _range(self, row, column):
        try:
            value = float(self.table.item(row, column).text())
        except (TypeError, ValueError):
            raise ValueError("range values must be numeric")
        if not 0.0 <= value <= 1.0:
            raise ValueError("range values must be between 0 and 1")
        return value

    def accept(self):
        """Validate all edits, then apply the complete network atomically."""
        validate_network_for_edit(self.network)
        values = []
        for row, seam in enumerate(self._seams):
            start_a, end_a = self._range(row, 2), self._range(row, 3)
            start_b, end_b = self._range(row, 6), self._range(row, 7)
            if start_a >= end_a or start_b >= end_b:
                raise ValueError("seam ranges must have positive extent")
            values.append((seam, start_a, end_a, start_b, end_b))
        alignment = str(self.alignment.currentText())
        reversed_b = bool(self.reversed_b.isChecked())
        for seam, start_a, end_a, start_b, end_b in values:
            seam.StartA, seam.EndA = start_a, end_a
            seam.StartB, seam.EndB = start_b, end_b
            seam.Alignment = alignment
            seam.ReversedB = reversed_b
        self.App.ActiveDocument.recompute()
        if network_reference_errors(self.network):
            raise ValueError("sewing network became invalid after edit")
        self._refresh_status()
        return True

    def reject(self):
        self.App.ActiveDocument.recompute()
        return True

    def _refresh_status(self):
        errors = network_reference_errors(self.network)
        self.status.setText(
            "%s | segments: %d | Δ %.3f mm%s"
            % (
                str(getattr(self.network, "Status", "")),
                int(getattr(self.network, "SegmentCount", 0)),
                float(getattr(self.network, "LengthDifference", 0.0)),
                " | invalid: " + ", ".join("%s (%s)" % item for item in errors) if errors else "",
            )
        )

    def getStandardButtons(self):
        _App, _Gui, _QtCore, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_sewing_network_task(network):
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = SewingNetworkTaskPanel(network)
    Gui.Control.showDialog(panel)
    return panel

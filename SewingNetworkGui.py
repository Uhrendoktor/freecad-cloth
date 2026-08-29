"""FreeCAD task panel for editing semantic sewing-network ranges."""


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


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

        seams = tuple(getattr(network, "Seams", ()) or ())
        self.table = QtWidgets.QTableWidget(len(seams), 8)
        self.table.setHorizontalHeaderLabels(("A piece", "A edge", "A start", "A end", "B piece", "B edge", "B start", "B end"))
        self.table.setObjectName("ClothSewingNetworkRangeTable")
        self._seams = seams
        for row, seam in enumerate(seams):
            values = (
                str(getattr(seam, "PieceA", "")),
                str(getattr(seam, "EdgeA", "")),
                float(getattr(seam, "StartA", 0.0)),
                float(getattr(seam, "EndA", 1.0)),
                str(getattr(seam, "PieceB", "")),
                str(getattr(seam, "EdgeB", "")),
                float(getattr(seam, "StartB", 0.0)),
                float(getattr(seam, "EndB", 1.0)),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if column in (2, 3, 6, 7):
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                else:
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
        for row, seam in enumerate(self._seams):
            start_a, end_a = self._range(row, 2), self._range(row, 3)
            start_b, end_b = self._range(row, 6), self._range(row, 7)
            if start_a >= end_a or start_b >= end_b:
                raise ValueError("seam ranges must have positive extent")
            seam.StartA, seam.EndA = start_a, end_a
            seam.StartB, seam.EndB = start_b, end_b
        self.App.ActiveDocument.recompute()
        self._refresh_status()
        return True

    def reject(self):
        self.App.ActiveDocument.recompute()
        return True

    def _refresh_status(self):
        self.status.setText(
            "%s | segments: %d | Δ %.3f mm"
            % (
                str(getattr(self.network, "Status", "")),
                int(getattr(self.network, "SegmentCount", 0)),
                float(getattr(self.network, "LengthDifference", 0.0)),
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

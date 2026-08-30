"""Native FreeCAD task panel for inspecting the complete sewing graph."""


def _modules():
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return Gui, QtWidgets


class SewingGraphTaskPanel:
    def __init__(self, document):
        from SewingValidation import validate_sewing_graph
        Gui, QtWidgets = _modules()
        self.Gui = Gui
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.form)
        self.report = validate_sewing_graph(document)
        self.summary = QtWidgets.QLabel(self.report["message"])
        self.summary.setWordWrap(True)
        self.summary.setObjectName("ClothSewingGraphSummary")
        layout.addWidget(self.summary)
        columns = ("Seam / network", "A", "B", "Status", "Length Δ")
        rows = list(self.report["seams"])
        self.table = QtWidgets.QTableWidget(len(rows) + len(self.report["networks"]), len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setObjectName("ClothSewingGraphTable")
        row = 0
        for item in rows:
            values = (item["id"], item["piece_a"], item["piece_b"], item["status"], "%.3f mm" % item["difference"])
            for col, value in enumerate(values):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))
            row += 1
        for item in self.report["networks"]:
            values = (item["id"], "network", "network", item["status"], "%.3f mm" % item["difference"])
            for col, value in enumerate(values):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))
            row += 1
        layout.addWidget(self.table)
        self.isolated = QtWidgets.QLabel(
            "Unsewn pieces: " + (", ".join(self.report["isolated"]) if self.report["isolated"] else "none")
        )
        self.isolated.setWordWrap(True)
        layout.addWidget(self.isolated)
        self.refresh = QtWidgets.QPushButton("Refresh validation")
        self.refresh.clicked.connect(self.update)
        layout.addWidget(self.refresh)

    def update(self):
        from SewingValidation import validate_sewing_graph
        self.report = validate_sewing_graph(self.Gui.activeDocument().Document)
        self.summary.setText(self.report["message"])
        self.isolated.setText("Unsewn pieces: " + (", ".join(self.report["isolated"]) if self.report["isolated"] else "none"))
        return self.report

    def getStandardButtons(self):
        _Gui, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Close


def show_sewing_graph_task(document):
    _Gui, _QtWidgets = _modules()
    panel = SewingGraphTaskPanel(document)
    _Gui.Control.showDialog(panel)
    return panel

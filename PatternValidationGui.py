"""FreeCAD task panel for persisted pattern topology validation."""


def _qt():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return QtWidgets


class PatternValidationTaskPanel:
    def __init__(self, obj, result=None):
        import PatternValidation
        QtWidgets = _qt()
        self.obj = obj
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — Validate Piece")
        layout = QtWidgets.QVBoxLayout(self.form)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.details = QtWidgets.QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.message)
        layout.addWidget(self.details)
        button = QtWidgets.QPushButton("Revalidate")
        button.clicked.connect(self.validate)
        layout.addWidget(button)
        self.validate(result)

    def validate(self, _result=None):
        import PatternValidation
        result = PatternValidation.validate_piece(self.obj)
        self.status.setText("Status: %s" % result["status"])
        self.message.setText(result["message"])
        if result["valid"]:
            self.details.setText("Boundary edges: %d\nSewing perimeter: %.2f mm" %
                                 (result["edge_count"], result["perimeter"]))
        else:
            self.details.setText("Repair the Sketcher boundary, recompute, and revalidate.")
        self.obj.Document.recompute()
        return result

    def accept(self):
        self.validate()
        return True

    def reject(self):
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


def show_pattern_validation_task(obj, result=None):
    import FreeCADGui as Gui
    panel = PatternValidationTaskPanel(obj, result)
    Gui.Control.showDialog(panel)
    return panel

"""FreeCAD CI compatibility shims loaded before test scripts."""

try:
    from PySide6 import QtGui
except ImportError:
    QtGui = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):

        def _pixel(self, x, y):
            return self.toImage().pixel(x, y)

        QPixmap.pixel = _pixel

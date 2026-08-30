"""FreeCAD CI compatibility shims loaded before test scripts."""

# Qt 6 removed QPixmap.pixel(); pixel data is exposed through QImage instead.
# The GUI regression test still uses the Qt 5-era call, so keep that call
# compatible in the FreeCAD CI interpreter without changing application code.
try:
    from PySide6 import QtGui
except Exception:
    QtGui = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):
        def _pixel(self, x, y):
            return self.toImage().pixel(x, y)

        try:
            QPixmap.pixel = _pixel
        except (AttributeError, TypeError):
            pass

"""FreeCAD CI compatibility shims loaded before test scripts."""

try:
    from PySide6 import QtGui
except ImportError:
    QtGui = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):

        def _pixel(self: QtGui.QPixmap, x: int, y: int) -> int:
            """Read a pixel through the backing QImage for older PySide compatibility.

            Args:
                self: Pixmap whose pixel value is requested.
                x: Horizontal pixel coordinate.
                y: Vertical pixel coordinate.

            Returns:
                Packed pixel value returned by the backing image.
            """
            return self.toImage().pixel(x, y)

        QPixmap.pixel = _pixel

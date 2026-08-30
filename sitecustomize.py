"""CI-only compatibility hooks for FreeCAD GUI regression runs."""
import os


if os.environ.get("CLOTH_SCREENSHOT_DIR"):
    try:
        from PySide2 import QtGui

        if not hasattr(QtGui.QPixmap, "pixel"):
            def _pixmap_pixel(self, x, y):
                return self.toImage().pixel(x, y)

            QtGui.QPixmap.pixel = _pixmap_pixel
    except Exception:
        # The hook must never prevent FreeCAD from starting.
        pass

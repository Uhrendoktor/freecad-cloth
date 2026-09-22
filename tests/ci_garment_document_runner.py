"""CI runner for the native Garment document contract.

Keeps tests/test_garment_document.py unchanged while providing the real FreeCAD
GUI environment and deterministic application teardown required by AppRun.
"""
import runpy
import sys

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

import FreeCAD as App
import FreeCADGui as Gui

sys.path.insert(0, "/workspace")

try:
    runpy.run_path("/workspace/tests/test_garment_document.py", run_name="__main__")
finally:
    for name in list(App.listDocuments()):
        try:
            App.closeDocument(name)
        except Exception:
            pass
    window = Gui.getMainWindow()
    if window is not None:
        window.close()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.quit()

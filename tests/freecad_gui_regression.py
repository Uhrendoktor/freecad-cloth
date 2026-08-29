"""Full-window GUI regression for the Cloth Pattern/Sewing/Simulation workbenches.

Run this file inside a real FreeCAD GUI process under Xvfb.  It deliberately
checks workbench chrome and task-panel visibility rather than only rendering
an active 3D view.
"""
import json
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_GUI_REGRESSION_DIR", os.path.join(ROOT, "docs/images/generated"))
os.makedirs(OUT, exist_ok=True)

DIAGNOSTICS = os.path.join(OUT, "gui-regression.json")


def _flush():
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def _toolbar_for(workbench):
    main = Gui.getMainWindow()
    candidates = []
    for toolbar in main.findChildren(QtWidgets.QToolBar):
        title = str(toolbar.windowTitle() or toolbar.objectName())
        if workbench in title:
            toolbar.show()
            candidates.append(toolbar)
    if not candidates:
        raise AssertionError("no visible toolbar found for %s" % workbench)
    return candidates[0]


def _combo_view():
    main = Gui.getMainWindow()
    for dock in main.findChildren(QtWidgets.QDockWidget):
        title = str(dock.windowTitle() or dock.objectName())
        if "Combo View" in title:
            dock.show()
            return dock
    raise AssertionError("FreeCAD Combo View dock is not present")


def _capture(name, expected_toolbar, panel):
    _flush()
    toolbar = _toolbar_for(expected_toolbar)
    combo = _combo_view()
    if not toolbar.isVisible():
        raise AssertionError("%s toolbar is hidden" % expected_toolbar)
    if not combo.isVisible():
        raise AssertionError("Combo View is hidden")
    if panel is not None and not panel.form.isVisible():
        raise AssertionError("task panel form is not visible for %s" % expected_toolbar)

    action_text = [str(action.text()) for action in toolbar.actions() if action.text()]
    path = os.path.join(OUT, name + ".png")
    if not Gui.getMainWindow().grab().save(path):
        raise AssertionError("failed to save %s" % path)
    return {
        "workbench": str(Gui.activeWorkbench()),
        "toolbar": str(toolbar.windowTitle() or toolbar.objectName()),
        "toolbar_actions": action_text,
        "toolbar_visible": bool(toolbar.isVisible()),
        "combo_view_visible": bool(combo.isVisible()),
        "task_panel_visible": bool(panel is not None and panel.form.isVisible()),
        "window_size": [Gui.getMainWindow().width(), Gui.getMainWindow().height()],
        "screenshot": path,
    }


def _close_task():
    try:
        Gui.Control.closeDialog()
    except (AttributeError, RuntimeError):
        pass
    _flush()


def run():
    doc = App.newDocument("ClothGuiRegression")
    results = {}
    try:
        from PatternCommands import create_pattern_piece_from_parameters
        from PatternGui import show_pattern_piece_task
        from PatternCommands import add_seam
        from SewingCommands import create_sewing_operation
        from SewingGui import show_sewing_task
        from SimulationObjects import create_simulation_scene
        from SimulationGui import show_simulation_task

        front = create_pattern_piece_from_parameters("Front", 140, 90, 8, 0)
        back = create_pattern_piece_from_parameters("Back", 140, 90, 8, 0)
        back.Placement.Base.x = 170
        doc.recompute()

        Gui.activateWorkbench("Cloth Pattern")
        panel = show_pattern_piece_task(front)
        results["pattern"] = _capture("cloth-gui-pattern", "Cloth Pattern", panel)
        _close_task()

        seam = add_seam()
        doc.recompute()
        operation = create_sewing_operation()
        Gui.activateWorkbench("Cloth Sewing")
        panel = show_sewing_task(operation)
        results["sewing"] = _capture("cloth-gui-sewing", "Cloth Sewing", panel)
        _close_task()

        scene = create_simulation_scene(doc)
        doc.recompute()
        Gui.activateWorkbench("Cloth Simulation")
        panel = show_simulation_task(scene)
        results["simulation"] = _capture("cloth-gui-simulation", "Cloth Simulation", panel)

        for state, data in results.items():
            if data["window_size"] != [1280, 720]:
                raise AssertionError("%s window geometry changed: %r" % (state, data["window_size"]))
            if not data["toolbar_actions"]:
                raise AssertionError("%s toolbar has no registered actions" % state)

        with open(DIAGNOSTICS, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2, sort_keys=True)
        return results
    except Exception:
        with open(DIAGNOSTICS, "w", encoding="utf-8") as handle:
            json.dump({"error": traceback.format_exc(), "partial": results}, handle, indent=2, sort_keys=True)
        raise
    finally:
        _close_task()
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


results = run()
print(json.dumps(results, indent=2, sort_keys=True))
main = Gui.getMainWindow()
if main is not None:
    main.close()

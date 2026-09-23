"""Isolated FreeCAD 1.1 activation-boundary probe for issue #1106.
The probe records runtime behavior without treating activation failure as test failure.
"""
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui


def probe(label, fn):
    print("probe=%s begin" % label, flush=True)
    try:
        result = fn()
        print("probe=%s pass result=%r" % (label, result), flush=True)
    except BaseException as exc:
        print("probe=%s fail type=%s message=%s" % (label, type(exc).__name__, exc), flush=True)
        traceback.print_exc()
    return


def active_name():
    try:
        wb = Gui.activeWorkbench()
        return None if wb is None else wb.name()
    except BaseException as exc:
        return "%s:%s" % (type(exc).__name__, exc)


print("runtime-freecad-version=%r" % (App.Version(),), flush=True)
print("runtime-python=%s" % sys.version.split()[0], flush=True)
print("gui-activateWorkbench=%s" % hasattr(Gui, "activateWorkbench"), flush=True)
print("gui-showMainWindow=%s" % hasattr(Gui, "showMainWindow"), flush=True)
print("gui-getMainWindow=%s" % hasattr(Gui, "getMainWindow"), flush=True)
print("gui-activeWorkbench=%s" % hasattr(Gui, "activeWorkbench"), flush=True)
print("initial-active-workbench=%r" % active_name(), flush=True)
print("initial-sketcher-registered=%s" % ("SketcherWorkbench" in Gui.listWorkbenches()), flush=True)

probe("Gui.showMainWindow", Gui.showMainWindow)
mw = Gui.getMainWindow()
print("main-window-type=%r" % (type(mw),), flush=True)
print("main-window-activateWorkbench=%s" % (mw is not None and hasattr(mw, "activateWorkbench")), flush=True)
print("post-show-gui-activateWorkbench=%s" % hasattr(Gui, "activateWorkbench"), flush=True)
print("post-show-active-workbench=%r" % active_name(), flush=True)

if mw is not None:
    probe("MainWindow.activateWorkbench:SketcherWorkbench",
          lambda: mw.activateWorkbench("SketcherWorkbench"))
    print("after-mainwindow-sketcher-active=%r" % active_name(), flush=True)

probe("Gui.activateWorkbench:SketcherWorkbench",
      lambda: Gui.activateWorkbench("SketcherWorkbench"))

try:
    import InitGui
    print("product-initgui-import=pass", flush=True)
except BaseException as exc:
    print("product-initgui-import=fail type=%s message=%s" % (type(exc).__name__, exc), flush=True)
    traceback.print_exc()

print("post-initgui-sketcher-registered=%s" % ("SketcherWorkbench" in Gui.listWorkbenches()), flush=True)
print("post-initgui-pattern-registered=%s" % ("ClothPatternWorkbench" in Gui.listWorkbenches()), flush=True)

if mw is not None:
    probe("MainWindow.activateWorkbench:ClothPatternWorkbench",
          lambda: mw.activateWorkbench("ClothPatternWorkbench"))
    print("after-mainwindow-pattern-active=%r" % active_name(), flush=True)

probe("newDocument-after-boundary",
      lambda: App.closeDocument(
          App.newDocument("ActivationBoundaryProbe").Name
      ))

print("probe-complete", flush=True)

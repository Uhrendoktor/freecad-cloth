"""Temporary boundary probe for the Native Sketcher GUI acceptance path."""
import math
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if entry not in ("", str(ROOT))]

def mark(stage: str) -> None:
    print("stage=" + stage, flush=True)

mark("script-loaded")
import FreeCAD as App  # noqa: E402
mark("freecad-imported")
import FreeCADGui as Gui  # noqa: E402
mark("freecadgui-imported")
import Part  # noqa: E402
mark("part-imported")

mark("process-start")
window = Gui.getMainWindow()
mark("main-window-read")
if window is None:
    raise RuntimeError("main window missing")
window.show()
mark("window-show")
Gui.updateGui()
mark("gui-updated")
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
QtWidgets.QApplication.processEvents()
mark("events-processed")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
init_gui = ROOT / "InitGui.py"
namespace = {"__file__": str(init_gui), "__name__": "__main__"}
mark("before-initgui-exec")
exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), namespace, namespace)
mark("after-initgui-exec")
if "ClothPatternWorkbench" not in Gui.listWorkbenches():
    raise RuntimeError("ClothPatternWorkbench not registered")
mark("workbenches-registered")

doc = App.newDocument("SketcherBoundaryProbe")
mark("document-created")

Gui.activateWorkbench("ClothPatternWorkbench")
mark("workbench-activated")
Gui.updateGui()
QtWidgets.QApplication.processEvents()
mark("workbench-events-processed")

commands = Gui.listCommands()
mark("commands-listed")
required = ["ClothPattern_CreatePieceWithSketch", "ClothPattern_EditSketch"]
missing = [name for name in required if name not in commands]
if missing:
    raise RuntimeError("missing commands: " + ",".join(missing))
mark("commands-validated")

Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
mark("create-command-returned")
Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
mark("second-create-command-returned")
doc.recompute()
pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
mark("pattern-pieces-count-" + str(len(pieces)))

curved = pieces[0]
mark("curved-piece-selected")
sketch = curved.Sketch
if sketch is None:
    raise RuntimeError("PatternPiece has no Sketch")
mark("piece-sketch-read")

sketch.Constraints = []
mark("constraints-cleared")

geometry = [
    Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
    Part.LineSegment(App.Vector(100, 0, 0), App.Vector(80, 50, 0)),
    Part.ArcOfCircle(Part.Circle(App.Vector(40, 50, 0), App.Vector(0, 0, 1), 40), 0, math.pi),
    Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
]
mark("geometry-built")

sketch.Geometry = geometry
mark("geometry-assigned")

sketch.SemanticEdgeIds = [f"{curved.PieceId}:edge:{i}" for i in range(4)]
mark("semantic-edges-assigned")

sketch.GeometryAuthority = "Sketcher"
mark("geometry-authority-assigned")

import Sketcher  # noqa: E402
sketch.addConstraint([
    Sketcher.Constraint("Coincident", 0, 2, 1, 1),
    Sketcher.Constraint("Coincident", 1, 2, 2, 1),
    Sketcher.Constraint("Coincident", 2, 2, 3, 1),
    Sketcher.Constraint("Coincident", 3, 2, 0, 1),
    Sketcher.Constraint("Horizontal", 0),
])
mark("geometric-constraints-added")

width_index = sketch.addConstraint(Sketcher.Constraint("Distance", 0, 100.0))
mark("width-constraint-added")
height_index = sketch.addConstraint(Sketcher.Constraint("Distance", 3, 50.0))
mark("height-constraint-added")

doc.recompute()
mark("sketch-recompute-complete")

audit = doc.addObject("Sketcher::SketchObject", "SketchConstraintAudit")
audit.Label = "Sketcher Constraint Audit"
mark("audit-sketch-created")

lines = [
    Part.LineSegment(App.Vector(0, 0, 0), App.Vector(40, 0, 0)),
    Part.LineSegment(App.Vector(0, 30, 0), App.Vector(40, 30, 0)),
    Part.LineSegment(App.Vector(20, -15, 0), App.Vector(20, 45, 0)),
    Part.Point(App.Vector(10, 0, 0)),
    Part.Point(App.Vector(30, 0, 0)),
    Part.LineSegment(App.Vector(0, 70, 0), App.Vector(40, 70, 0)),
    Part.LineSegment(App.Vector(0, 80, 0), App.Vector(20, 80, 0)),
]
audit.addGeometry(lines, False)
mark("audit-geometry-added")

audit.toggleConstruction(2)
mark("audit-construction-toggled")

equal_index = audit.addConstraint(Sketcher.Constraint("Equal", 0, 1))
audit.addConstraint(Sketcher.Constraint("Horizontal", 0))
audit.addConstraint(Sketcher.Constraint("Horizontal", 1))
audit.addConstraint(Sketcher.Constraint("Vertical", 2))
mark("audit-basic-constraints-added")

point_on_object_index = audit.addConstraint(Sketcher.Constraint("PointOnObject", 3, 1, 0))
mark("audit-point-on-object-added")
symmetric_index = audit.addConstraint(Sketcher.Constraint("Symmetric", 3, 1, 4, 1, 2, 1))
mark("audit-symmetric-added")
audit_span = audit.addConstraint(Sketcher.Constraint("Distance", 5, 40.0))
mark("audit-span-added")
audit_scaled = audit.addConstraint(Sketcher.Constraint("Distance", 6, 20.0))
mark("audit-scaled-added")

audit.renameConstraint(audit_span, "AuditSpan")
audit.renameConstraint(audit_scaled, "AuditScaled")
mark("audit-constraint-names-set")
audit.setExpression("Constraints[%d]" % audit_scaled, "Constraints[%d] / 2" % audit_span)
mark("audit-expression-set")
doc.recompute()
mark("audit-recompute-complete")

geometry_count = len(audit.Geometry)
audit.addExternal(curved.Sketch.Name, "Edge1")
mark("audit-external-added")
if len(audit.Geometry) != geometry_count:
    raise RuntimeError("external geometry unexpectedly changed owned geometry")
if not getattr(audit, "ExternalGeometry", ()):
    raise RuntimeError("external geometry did not persist")
mark("audit-external-validated")

curved.Placement.Base.x = -130
pieces[1].Placement.Base.x = 20
mark("piece-placements-set")

Gui.Selection.clearSelection()
Gui.Selection.addSelection(curved)
mark("pattern-piece-selected-for-edit")
Gui.runCommand("ClothPattern_EditSketch", 0)
mark("edit-sketch-command-returned")
Gui.updateGui()
QtWidgets.QApplication.processEvents()
mark("edit-sketch-events-processed")
if not Gui.activeDocument().getInEdit():
    raise RuntimeError("PatternPiece edit command did not enter Sketcher")
mark("edit-sketch-entered")
Gui.activeDocument().resetEdit()
Gui.updateGui()
QtWidgets.QApplication.processEvents()
mark("edit-sketch-reset")

mark("sketcher-imported")

sketch = doc.addObject("Sketcher::SketchObject", "BoundarySketch")
doc.recompute()
if sketch is None:
    raise RuntimeError("Sketcher object creation returned None")
mark("sketch-object-created")

App.closeDocument(doc.Name)
mark("document-closed")

_run_direct_seam_edit_case()

app = QtWidgets.QApplication.instance()
if app is not None:
    app.quit()
def _diag_mark(label):
    print("diag-marker=%s t=%.6f" % (label, time.monotonic()), flush=True)

def _diag_state(label):
    doc = App.ActiveDocument
    gui_doc = Gui.activeDocument()
    in_edit = None
    if gui_doc is not None:
        try:
            in_edit = bool(gui_doc.getInEdit())
        except Exception as exc:
            in_edit = "error:%s" % type(exc).__name__
    try:
        dialog = Gui.Control.activeDialog()
    except Exception as exc:
        dialog = "error:%s" % type(exc).__name__
    if dialog is None:
        dialog_desc = "none"
    else:
        try:
            dialog_desc = "%s visible=%s objectName=%s" % (
                type(dialog).__name__,
                bool(dialog.isVisible()) if hasattr(dialog, "isVisible") else "na",
                str(dialog.objectName()) if hasattr(dialog, "objectName") else "na",
            )
        except Exception as exc:
            dialog_desc = "error:%s" % type(exc).__name__
    pending_tx = None
    tx_empty = None
    if doc is not None:
        fn = getattr(doc, "hasPendingTransaction", None)
        if callable(fn):
            try:
                pending_tx = bool(fn())
            except Exception as exc:
                pending_tx = "error:%s" % type(exc).__name__
        fn = getattr(doc, "isTransactionEmpty", None)
        if callable(fn):
            try:
                tx_empty = bool(fn())
            except Exception as exc:
                tx_empty = "error:%s" % type(exc).__name__
    pending_cmd = None
    command_cls = getattr(Gui, "Command", None)
    pending_fn = getattr(command_cls, "hasPendingCommand", None) if command_cls is not None else None
    if callable(pending_fn):
        try:
            pending_cmd = bool(pending_fn())
        except Exception as exc:
            pending_cmd = "error:%s" % type(exc).__name__
    _diag_mark(
        "state label=%s in_edit=%s activeDialog=%s pendingTx=%s txEmpty=%s pendingCommand=%s"
        % (label, in_edit, dialog_desc, pending_tx, tx_empty, pending_cmd)
    )

def _run_direct_seam_edit_case():
    import os
    import threading
    import time
    import traceback

    watchdog_stop = threading.Event()

    def _watchdog():
        if not watchdog_stop.wait(20.0):
            _diag_mark("watchdog-fired")
            os._exit(124)

    threading.Thread(target=_watchdog, name="seam-edit-diagnostic-watchdog", daemon=True).start()
    acceptance = ROOT / "tests" / "freecad_sketcher_acceptance.py"
    sewing_commands_path = ROOT / "freecad_cloth" / "sewing" / "SewingCommands.py"
    command_source = sewing_commands_path.read_text(encoding="utf-8")
    start = command_source.index("def _edit_selected_seam_side(side):")
    end = command_source.index("\ndef edit_selected_seam_side_a", start)
    handler_source = command_source[start:end]

    replacements = [
        (
            "    focus_selected_seam_3d()",
            "    _diag_mark(\"before-focus\")\n"
            "    _diag_state(\"before-focus\")\n"
            "    focus_selected_seam_3d()\n"
            "    _diag_mark(\"after-focus\")\n"
            "    _diag_state(\"after-focus\")",
        ),
        (
            "    if Gui.activeDocument().getInEdit():\n"
            "        Gui.activeDocument().resetEdit()",
            "    if Gui.activeDocument().getInEdit():\n"
            "        _diag_mark(\"before-reset-edit\")\n"
            "        _diag_state(\"before-reset-edit\")\n"
            "        Gui.activeDocument().resetEdit()\n"
            "        _diag_mark(\"after-reset-edit\")\n"
            "        _diag_state(\"after-reset-edit\")",
        ),
        (
            "    Gui.Selection.clearSelection()\n"
            "    Gui.Selection.addSelection(piece)\n"
            "    Gui.activeDocument().setEdit(sketch.Name)",
            "    _diag_mark(\"before-patternpiece-selection\")\n"
            "    Gui.Selection.clearSelection()\n"
            "    _diag_mark(\"after-clear-selection-before-patternpiece\")\n"
            "    Gui.Selection.addSelection(piece)\n"
            "    _diag_mark(\"after-patternpiece-selection\")\n"
            "    _diag_state(\"before-set-edit\")\n"
            "    try:\n"
            "        from PySide import QtCore, QtWidgets\n"
            "    except ImportError:\n"
            "        from PySide2 import QtCore, QtWidgets\n"
            "    _diag_mark(\"before-set-edit-events\")\n"
            "    QtWidgets.QApplication.processEvents()\n"
            "    _diag_mark(\"after-pre-set-edit-events\")\n"
            "    QtCore.QTimer.singleShot(100, lambda: _diag_mark(\"timer-during-set-edit\"))\n"
            "    _diag_mark(\"before-set-edit\")\n"
            "    Gui.activeDocument().setEdit(sketch.Name)\n"
            "    _diag_mark(\"after-set-edit\")\n"
            "    _diag_state(\"after-set-edit\")\n"
            "    QtWidgets.QApplication.processEvents()\n"
            "    _diag_mark(\"after-set-edit-events\")",
        ),
        (
            '    Gui.Selection.clearSelection()\n    Gui.Selection.addSelection(sketch, "Edge%d" % (edge_index + 1))',
            '    _diag_mark("before-edge-selection")\n'
            '    Gui.Selection.clearSelection()\n'
            '    _diag_mark("after-edge-clear-selection")\n'
            '    Gui.Selection.addSelection(sketch, "Edge%d" % (edge_index + 1))\n'
            '    _diag_mark("after-edge-selection")\n'
            '    _diag_state("after-edge-selection")',
        ),
    ]
    for needle, replacement in replacements:
        if handler_source.count(needle) != 1:
            raise RuntimeError("diagnostic handler transform expected exactly one %r" % needle)
        handler_source = handler_source.replace(needle, replacement, 1)

    import freecad_cloth.sewing.SewingCommands as SewingCommands
    handler_globals = dict(vars(SewingCommands))
    handler_globals.update({
        "_diag_mark": _diag_mark,
        "_diag_state": _diag_state,
    })
    exec(compile(handler_source, str(sewing_commands_path), "exec"), handler_globals, handler_globals)
    instrumented_handler = handler_globals["_edit_selected_seam_side"]

    acceptance_source = acceptance.read_text(encoding="utf-8")
    command_needle = '        Gui.runCommand("ClothSewing_EditSeamSideA", 0)'
    command_replacement = (
        '        _diag_mark("before-direct-acceptance-run")\n'
        '        _diag_state("before-direct-acceptance-run")\n'
        '        _diag_instrumented_handler("A")\n'
        '        _record("diag-direct-handler-returned")\n'
        '        _diag_mark("after-direct-handler")\n'
        '        _diag_state("after-direct-handler")\n'
        '        return'
    )
    if acceptance_source.count(command_needle) != 1:
        raise RuntimeError("acceptance seam edit command expected exactly once")
    acceptance_source = acceptance_source.replace(command_needle, command_replacement, 1)
    autorun = (
        "\ntry:\n"
        "    run_acceptance()\n"
        "except BaseException:\n"
        "    _quit_application()\n"
        "    raise\n"
    )
    if autorun not in acceptance_source:
        raise RuntimeError("acceptance autorun block changed unexpectedly")
    acceptance_source = acceptance_source.replace(autorun, "\n", 1)

    namespace = {
        "__name__": "__diag_acceptance__",
        "__file__": str(acceptance),
        "_diag_instrumented_handler": instrumented_handler,
        "_diag_mark": _diag_mark,
        "_diag_state": _diag_state,
    }
    exec(compile(acceptance_source, str(acceptance), "exec"), namespace, namespace)
    try:
        _diag_mark("before-direct-acceptance")
        namespace["run_acceptance"]()
    except BaseException:
        _diag_mark("direct-acceptance-exception")
        traceback.print_exc()
    finally:
        watchdog_stop.set()
        doc = App.ActiveDocument
        if doc is not None:
            try:
                App.closeDocument(doc.Name)
            except Exception:
                pass
        _events()
        _diag_mark("direct-acceptance-finished")

mark("quit-requested")

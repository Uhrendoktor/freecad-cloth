def _run_exact_seam_edit_cases():
    import os
    import shutil
    import subprocess
    import tempfile
    import time

    acceptance = ROOT / "tests" / "freecad_sketcher_acceptance.py"
    source = acceptance.read_text(encoding="utf-8")
    helper = "def _diag_mark(label):\n    print(\"diag-marker=%s t=%.6f\" % (label, time.monotonic()), flush=True)\n\ndef _diag_state(label):\n    doc = App.ActiveDocument\n    gui_doc = Gui.activeDocument()\n    in_edit = None\n    if gui_doc is not None:\n        try:\n            in_edit = bool(gui_doc.getInEdit())\n        except Exception as exc:\n            in_edit = \"error:%s\" % type(exc).__name__\n    try:\n        dialog = Gui.Control.activeDialog()\n    except Exception as exc:\n        dialog = \"error:%s\" % type(exc).__name__\n    if dialog is None:\n        dialog_desc = \"none\"\n    else:\n        try:\n            dialog_desc = \"%s visible=%s objectName=%s\" % (type(dialog).__name__, bool(dialog.isVisible()) if hasattr(dialog, \"isVisible\") else \"na\", str(dialog.objectName()) if hasattr(dialog, \"objectName\") else \"na\")\n        except Exception as exc:\n            dialog_desc = \"error:%s\" % type(exc).__name__\n    pending_tx = None\n    tx_empty = None\n    if doc is not None:\n        fn = getattr(doc, \"hasPendingTransaction\", None)\n        if callable(fn):\n            try:\n                pending_tx = bool(fn())\n            except Exception as exc:\n                pending_tx = \"error:%s\" % type(exc).__name__\n        fn = getattr(doc, \"isTransactionEmpty\", None)\n        if callable(fn):\n            try:\n                tx_empty = bool(fn())\n            except Exception as exc:\n                tx_empty = \"error:%s\" % type(exc).__name__\n    pending_cmd = None\n    command_cls = getattr(Gui, \"Command\", None)\n    pending_fn = getattr(command_cls, \"hasPendingCommand\", None) if command_cls is not None else None\n    if callable(pending_fn):\n        try:\n            pending_cmd = bool(pending_fn())\n        except Exception as exc:\n            pending_cmd = \"error:%s\" % type(exc).__name__\n    _diag_mark(\"state label=%s in_edit=%s activeDialog=%s pendingTx=%s txEmpty=%s pendingCommand=%s\" % (label, in_edit, dialog_desc, pending_tx, tx_empty, pending_cmd))\n\n"
    cases = {"command":"        _diag_mark(\"before-command\")\n        _diag_state(\"before-command\")\n        Gui.runCommand(\"ClothSewing_EditSeamSideA\", 0)\n        _diag_mark(\"after-command\")\n        _diag_state(\"after-command\")\n        return","direct":"        _diag_mark(\"before-direct-handler\")\n        _diag_state(\"before-direct-handler\")\n        from freecad_cloth.sewing.SewingCommands import edit_selected_seam_side_a\n        edit_selected_seam_side_a()\n        _diag_mark(\"after-direct-handler\")\n        _diag_state(\"after-direct-handler\")\n        return","instrumented":"        _diag_mark(\"instrumented-entry\")\n        _diag_state(\"before-focus\")\n        _diag_mark(\"before-focus\")\n        from freecad_cloth.sewing.SewingCommands import focus_selected_seam_3d\n        focus_selected_seam_3d()\n        _diag_mark(\"after-focus\")\n        _diag_state(\"after-focus\")\n        if Gui.activeDocument().getInEdit():\n            _diag_mark(\"before-reset-edit\")\n            Gui.activeDocument().resetEdit()\n            _diag_mark(\"after-reset-edit\")\n            _diag_state(\"after-reset-edit\")\n        _events()\n        _diag_mark(\"after-pre-setedit-events\")\n        _diag_state(\"before-patternpiece-selection\")\n        Gui.Selection.clearSelection()\n        _diag_mark(\"after-clear-selection-before-patternpiece\")\n        Gui.Selection.addSelection(curved)\n        _diag_mark(\"after-patternpiece-selection\")\n        _diag_state(\"before-set-edit\")\n        try:\n            from PySide import QtCore\n        except ImportError:\n            from PySide2 import QtCore\n        QtCore.QTimer.singleShot(100, lambda: _diag_mark(\"timer-during-set-edit\"))\n        _diag_mark(\"before-set-edit\")\n        Gui.activeDocument().setEdit(sketch.Name)\n        _diag_mark(\"after-set-edit\")\n        _diag_state(\"after-set-edit\")\n        _events()\n        _diag_mark(\"after-set-edit-events\")\n        _diag_state(\"after-set-edit-events\")\n        Gui.Selection.clearSelection()\n        _diag_mark(\"after-edge-clear-selection\")\n        Gui.Selection.addSelection(sketch, \"Edge%d\" % (edge_index + 1))\n        _diag_mark(\"after-edge-selection\")\n        _diag_state(\"after-edge-selection\")\n        return"}
    insertion = "\ndef _bootstrap_workbenches():"
    for case in ("command", "direct", "instrumented"):
        case_source = source.replace(insertion, "\n" + helper + insertion, 1)
        needle = '        Gui.runCommand("ClothSewing_EditSeamSideA", 0)'
        if case_source.count(needle) != 1:
            raise RuntimeError("seam edit command not found exactly once for %s" % case)
        case_source = case_source.replace(needle, cases[case], 1)

        workdir = tempfile.mkdtemp(prefix="freecad-seam-diag-")
        user_home = os.path.join(workdir, "home")
        user_data = os.path.join(workdir, "data")
        user_temp = os.path.join(workdir, "temp")
        xdg_runtime = os.path.join(workdir, "runtime")
        for directory in (user_home, user_data, user_temp, xdg_runtime):
            os.makedirs(directory, exist_ok=True)
        case_file = None
        try:
            fd, case_file = tempfile.mkstemp(prefix=".sketcher_seam_diag_", suffix=".py", dir=str(ROOT / "tests"))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("import time\n" + case_source)
            env = os.environ.copy()
            env.update({
                "FREECAD_USER_HOME": user_home,
                "FREECAD_USER_DATA": user_data,
                "FREECAD_USER_TEMP": user_temp,
                "XDG_RUNTIME_DIR": xdg_runtime,
                "PYTHONUNBUFFERED": "1",
            })
            started = time.monotonic()
            proc = subprocess.run(
                ["timeout", "--signal=TERM", "--kill-after=2s", "5s", "/opt/freecad/AppRun", case_file],
                cwd=str(ROOT),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            elapsed = time.monotonic() - started
            print("=== seam-edit-diagnostic case=%s exit=%s elapsed=%.3fs ===" % (case, proc.returncode, elapsed), flush=True)
            print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n", flush=True)
            markers = [
                line for line in proc.stdout.splitlines()
                if line.startswith("diag-marker=") or line.startswith("stage=") or line.startswith("sketcher-acceptance=")
            ]
            print("case=%s last-marker=%s" % (case, markers[-1] if markers else "<none>"), flush=True)
        finally:
            if case_file:
                try:
                    os.unlink(case_file)
                except FileNotFoundError:
                    pass
            shutil.rmtree(workdir, ignore_errors=True)

"""Temporary boundary probe for the Native Sketcher GUI acceptance path."""
import math
import os
import sys
import tempfile
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

_run_exact_seam_edit_cases()

app = QtWidgets.QApplication.instance()
if app is not None:
    app.quit()
mark("quit-requested")

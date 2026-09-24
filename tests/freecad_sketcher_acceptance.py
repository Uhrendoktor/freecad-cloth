"""Canonical FreeCAD/Xvfb acceptance for native Sketcher pattern authoring."""
import math
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if entry not in ("", str(ROOT))]

print("stage=script-loaded", flush=True)
import FreeCAD as App
print("stage=freecad-imported", flush=True)
import FreeCADGui as Gui
print("stage=freecadgui-imported", flush=True)
import Part
print("stage=part-imported", flush=True)
 

def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()


def _close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        _events()


def _activate(name, commands):
    Gui.activateWorkbench(name)
    _events()
    if Gui.activeWorkbench().name() != name:
        raise RuntimeError("failed to activate %s" % name)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))


def _pattern_pieces(doc):
    return [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]


def _constraint_type(sketch, index):
    return str(getattr(sketch.Constraints[index], "Type", ""))


def _constraint_name(sketch, index):
    return str(getattr(sketch.Constraints[index], "Name", ""))


def _make_curved_piece_sketch(piece, doc):
    """Use native Sketcher geometry as the actual PatternPiece geometry authority."""
    import Sketcher
    sketch = piece.Sketch
    if sketch is None:
        raise RuntimeError("PatternPiece did not create a native Sketcher sketch")
    sketch.Constraints = []
    geometry = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(80, 50, 0)),
        Part.ArcOfCircle(Part.Circle(App.Vector(40, 50, 0), App.Vector(0, 0, 1), 40), 0, math.pi),
        Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
    ]
    sketch.Geometry = geometry
    sketch.SemanticEdgeIds = [f"{piece.PieceId}:edge:{i}" for i in range(4)]
    sketch.GeometryAuthority = "Sketcher"
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", 0, 2, 1, 1),
        Sketcher.Constraint("Coincident", 1, 2, 2, 1),
        Sketcher.Constraint("Coincident", 2, 2, 3, 1),
        Sketcher.Constraint("Coincident", 3, 2, 0, 1),
        Sketcher.Constraint("Horizontal", 0),
    ])
    width_index = sketch.addConstraint(Sketcher.Constraint("Distance", 0, 100.0))
    sketch.renameConstraint(width_index, "PieceWidth")
    height_index = sketch.addConstraint(Sketcher.Constraint("Distance", 3, 50.0))
    sketch.renameConstraint(height_index, "PieceHeight")
    doc.recompute()
    if sketch.Shape.isNull() or piece.Shape.isNull():
        raise RuntimeError("curved PatternPiece did not produce native geometry")
    if _constraint_type(sketch, width_index) != "Distance" or _constraint_type(sketch, height_index) != "Distance":
        raise RuntimeError("native dimensional constraints were not retained")
    if _constraint_name(sketch, width_index) != "PieceWidth" or _constraint_name(sketch, height_index) != "PieceHeight":
        raise RuntimeError("named Sketcher dimensions were not retained")
    if abs(float(sketch.getDatum(height_index)) - 50.0) > 1e-6:
        raise RuntimeError("named Sketcher height did not initialize to the expected value")
    if abs(float(sketch.getDatum(width_index)) - 100.0) > 1e-6:
        raise RuntimeError("named width dimension did not initialize as expected")
    return sketch, width_index, height_index


def _exercise_constraint_families(doc, reference_sketch):
    """Exercise native geometric constraints and expression references."""
    import Sketcher
    audit = doc.addObject("Sketcher::SketchObject", "SketchConstraintAudit")
    audit.Label = "Sketcher Constraint Audit"
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
    audit.toggleConstruction(2)
    if not bool(audit.GeometryFacadeList[2].Construction):
        raise RuntimeError("native construction geometry flag was not retained")

    equal_index = audit.addConstraint(Sketcher.Constraint("Equal", 0, 1))
    audit.addConstraint(Sketcher.Constraint("Horizontal", 0))
    audit.addConstraint(Sketcher.Constraint("Horizontal", 1))
    audit.addConstraint(Sketcher.Constraint("Vertical", 2))
    point_on_object_index = audit.addConstraint(Sketcher.Constraint("PointOnObject", 3, 1, 0))
    symmetric_index = audit.addConstraint(Sketcher.Constraint("Symmetric", 3, 1, 4, 1, 2, 1))
    audit_span = audit.addConstraint(Sketcher.Constraint("Distance", 5, 40.0))
    audit_scaled = audit.addConstraint(Sketcher.Constraint("Distance", 6, 20.0))
    audit.renameConstraint(audit_span, "AuditSpan")
    audit.renameConstraint(audit_scaled, "AuditScaled")
    audit.setExpression("Constraints[%d]" % audit_scaled, "Constraints[%d] / 2" % audit_span)
    for index, expected in ((equal_index, "Equal"), (point_on_object_index, "PointOnObject"), (symmetric_index, "Symmetric"), (audit_span, "Distance"), (audit_scaled, "Distance")):
        if _constraint_type(audit, index) != expected:
            raise RuntimeError("missing native %s constraint" % expected)
    doc.recompute()
    if abs(float(audit.getDatum(audit_scaled)) - 20.0) > 1e-6:
        raise RuntimeError("native Sketcher expression did not evaluate")
    if _constraint_name(audit, audit_span) != "AuditSpan" or _constraint_name(audit, audit_scaled) != "AuditScaled":
        raise RuntimeError("named native Sketcher expression drivers were not retained")

    geometry_count = len(audit.Geometry)
    audit.addExternal(reference_sketch.Name, "Edge1")
    if len(audit.Geometry) != geometry_count:
        raise RuntimeError("external geometry unexpectedly became owned sketch geometry")
    external = getattr(audit, "ExternalGeometry", ())
    if not external:
        raise RuntimeError("native external geometry reference was not persisted in the sketch")
    doc.recompute()
    return audit, audit_span, audit_scaled


def _stage(name):
    message = "stage=%s" % name
    print(message, flush=True)
    stage_file = os.environ.get("SKETCHER_STAGE_FILE")
    if stage_file:
        with open(stage_file, "a", encoding="utf-8") as handle:
            handle.write(message + "\n")
            handle.flush()


def _bootstrap_workbenches():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError(
            "FreeCAD GUI main window must be visible before workbench acceptance"
        )
    if "ClothPatternWorkbench" in Gui.listWorkbenches():
        return
    init_gui = ROOT / "InitGui.py"
    if not init_gui.is_file():
        raise RuntimeError("InitGui.py missing from FreeCAD workbench root")
    namespace = {"__file__": str(init_gui), "__name__": "__main__"}
    exec(
        compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"),
        namespace,
        namespace,
    )
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        raise RuntimeError("ClothPatternWorkbench was not registered by explicit InitGui startup")


def _record(message):
    line = "sketcher-acceptance=%s" % message
    print(line, flush=True)
    stage_file = os.environ.get("SKETCHER_STAGE_FILE")
    if stage_file:
        with open(stage_file, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()


def run_acceptance():
    _stage("process-start")
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD GUI main window is not available")
    window.show()
    _events()
    _stage("gui-ready")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _bootstrap_workbenches()
    _stage("workbenches-registered")
    doc = App.newDocument("NativeSketcherAcceptance")
    try:
        _stage("document-created")
        _activate("ClothPatternWorkbench", ["ClothPattern_CreatePieceWithSketch", "ClothPattern_EditSketch"])
        _record("pattern-workbench-ready")
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        doc.recompute()
        pieces = _pattern_pieces(doc)
        if len(pieces) != 2:
            raise RuntimeError("public Pattern command did not create two PatternPiece objects")
        if any(getattr(piece, "Sketch", None) is None for piece in pieces):
            raise RuntimeError("public Pattern command did not create one native Sketcher source per PatternPiece")
        _record("two-native-pattern-pieces")
        curved, mate = pieces
        curved.Placement.Base.x = -130
        mate.Placement.Base.x = 20
        curved_sketch, width_index, height_index = _make_curved_piece_sketch(curved, doc)
        reference = mate.Sketch
        if reference is None:
            raise RuntimeError("second PatternPiece has no native Sketcher source")
        audit, audit_span, audit_scaled = _exercise_constraint_families(doc, reference)
        _record("sketch-geometry-and-constraints")

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(curved)
        Gui.runCommand("ClothPattern_EditSketch", 0)
        _events()
        if not Gui.activeDocument().getInEdit():
            raise RuntimeError("public Pattern Edit Sketch command did not enter native Sketcher")
        Gui.activeDocument().resetEdit()
        _events()
        _record("pattern-sketch-edit-passed")

        _stage("before-sewing-activate")
        _activate("ClothSewingWorkbench", [
            "ClothSewing_CreateSeam",
            "ClothSewing_FocusSeam3D",
            "ClothSewing_EditSeamSideA",
        ])
        _stage("sewing-workbench-activated")
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(curved, "Edge3")
        Gui.Selection.addSelection(mate, "Edge1")
        _stage("before-seam-create-command")
        Gui.runCommand("ClothSewing_CreateSeam", 0)
        _stage("after-seam-create-command")
        doc.recompute()
        seam = next((obj for obj in doc.Objects if getattr(obj, "SeamId", "")), None)
        if seam is None or str(seam.Status) != "Valid":
            raise RuntimeError("public Sewing command did not create a valid seam from native Sketch edges")
        _record("seam-created")
        original_piece_id = str(curved.PieceId)
        original_width = float(curved_sketch.getDatum(width_index))
        seam_id = str(seam.SeamId)
        semantic_ids = tuple(str(item) for item in curved_sketch.SemanticEdgeIds)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(seam)
        _stage("before-seam-focus-command")
        Gui.runCommand("ClothSewing_FocusSeam3D", 0)
        _stage("after-seam-focus-command")
        if seam.Shape.isNull():
            raise RuntimeError("seam focus command did not retain world-space presentation geometry")
        from freecad_cloth.sewing.SewingView import seam_color_map
        expected_seam_rgb = tuple(seam_color_map([seam_id])[seam_id])
        actual_seam_rgb = tuple(seam.ViewObject.LineColor[:3])
        if any(abs(actual - expected) > 1e-6 for actual, expected in zip(actual_seam_rgb, expected_seam_rgb)):
            raise RuntimeError("seam focus command did not preserve deterministic seam color: actual=%r expected=%r" % (actual_seam_rgb, expected_seam_rgb))
        seam_box = seam.Shape.BoundBox
        placed_piece_box = curved.Shape.BoundBox
        if seam_box.XMax < placed_piece_box.XMin or seam_box.XMin > placed_piece_box.XMax:
            raise RuntimeError("seam presentation is outside the placed PatternPiece coordinate system")
        if abs(float(seam_box.XMin)) < 1e-6 and abs(float(seam_box.XMax)) < 1e-6:
            raise RuntimeError("seam presentation appears to remain at the source Sketcher origin")
        _record("seam-world-space-validated")
        seam_vertices = tuple(vertex.Point for vertex in seam.Shape.Vertexes)

        def _has_vertex(point, tolerance=1e-6):
            return any((vertex - point).Length <= tolerance for vertex in seam_vertices)

        # These are the explicit Sketcher fixture endpoints used above: curved Edge3 is
        # the semicircle from (80, 50) to (0, 50), while mate Edge1 is (0, 0) to
        # (100, 0). Applying each PatternPiece placement produces the expected
        # world-space seam endpoints without rebuilding the presentation geometry.
        world_edge_endpoints = (
            curved.Placement.multVec(App.Vector(80, 50, 0.4)),
            curved.Placement.multVec(App.Vector(0, 50, 0.4)),
            mate.Placement.multVec(App.Vector(0, 0, 0.4)),
            mate.Placement.multVec(App.Vector(100, 0, 0.4)),
        )
        for expected in world_edge_endpoints:
            if not _has_vertex(expected):
                raise RuntimeError(
                    "seam presentation does not contain the placed/world-space Sketcher seam endpoint: %s"
                    % expected
                )
        local_mate_start = App.Vector(0, 0, 0.4)
        if _has_vertex(local_mate_start):
            raise RuntimeError("seam presentation still contains the mate Sketcher endpoint in local coordinates")
        _stage("before-seam-edit-command")
        Gui.runCommand("ClothSewing_EditSeamSideA", 0)
        _stage("after-seam-edit-command")
        if not Gui.activeDocument().getInEdit():
            raise RuntimeError("seam Sketcher-side command did not enter native Sketcher")
        selection = Gui.Selection.getSelectionEx()
        sketch_selection = [item for item in selection if item.Object is curved.Sketch]
        if not sketch_selection or "Edge3" not in tuple(sketch_selection[-1].SubElementNames):
            raise RuntimeError("seam Sketcher-side command did not select the authoritative semantic edge")
        Gui.activeDocument().resetEdit()
        _events()

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "native-sketcher-acceptance.FCStd")
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            doc = None
            _stage("before-save-reload-open")
            reloaded = App.openDocument(path)
            _stage("after-save-reload-open")
            _record("save-reload-opened")
            curved = next((obj for obj in reloaded.Objects if str(getattr(obj, "PieceId", "")) == original_piece_id), None)
            if curved is None or curved.Sketch is None:
                raise RuntimeError("PatternPiece native Sketcher source did not survive save/reload")
            sketch = curved.Sketch
            if str(curved.GeometryAuthority) != "Sketcher":
                raise RuntimeError("Sketcher authority flag did not survive save/reload")
            if str(sketch.GeometryAuthority) != "Sketcher":
                raise RuntimeError("Sketcher source authority did not survive save/reload")
            if tuple(str(item) for item in sketch.SemanticEdgeIds) != semantic_ids:
                raise RuntimeError("Cloth semantic edge ids did not survive save/reload")
            if abs(float(sketch.getDatum(width_index)) - original_width) > 1e-6:
                raise RuntimeError("named width dimensional constraint did not survive save/reload")
            if abs(float(sketch.getDatum(height_index)) - 50.0) > 1e-6:
                raise RuntimeError("named height dimensional constraint did not survive save/reload")
            if _constraint_name(sketch, width_index) != "PieceWidth" or _constraint_name(sketch, height_index) != "PieceHeight":
                raise RuntimeError("named PatternPiece Sketcher dimensions did not survive save/reload")
            audit = reloaded.getObject("SketchConstraintAudit")
            if audit is None or not getattr(audit, "ExternalGeometry", ()):
                raise RuntimeError("external Sketcher reference did not survive save/reload")
            if not bool(audit.GeometryFacadeList[2].Construction):
                raise RuntimeError("construction geometry state did not survive save/reload")
            if _constraint_name(audit, audit_span) != "AuditSpan" or _constraint_name(audit, audit_scaled) != "AuditScaled":
                raise RuntimeError("named expression driver constraints did not survive save/reload")
            if abs(float(audit.getDatum(audit_scaled)) - 20.0) > 1e-6:
                raise RuntimeError("native Sketcher expression result did not survive save/reload")
            audit.setDatum(audit_span, App.Units.Quantity("60 mm"))
            reloaded.recompute()
            if abs(float(audit.getDatum(audit_scaled)) - 30.0) > 1e-6:
                raise RuntimeError("native Sketcher expression did not propagate after save/reload")

            sketch.setDatum(width_index, App.Units.Quantity("120 mm"))
            reloaded.recompute()
            if abs(float(sketch.getDatum(width_index)) - 120.0) > 1e-6:
                raise RuntimeError("native Sketcher seam dimension edit did not apply")
            changed_seam = next((obj for obj in reloaded.Objects if getattr(obj, "SeamId", "") == seam_id), None)
            if changed_seam is None:
                raise RuntimeError("seam did not survive save/reload")
            if str(changed_seam.Status) == "Valid":
                raise RuntimeError("native Sketcher edit did not invalidate downstream seam")
            _record("reload-and-invalidation-passed")
            App.closeDocument(reloaded.Name)
            doc = None
        print("native Sketcher acceptance passed", flush=True)
    finally:
        _close_task()
        if doc is not None:
            try:
                App.closeDocument(doc.Name)
            except Exception:
                pass
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()


def _quit_application():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.quit()


try:
    run_acceptance()
except BaseException:
    _quit_application()
    raise
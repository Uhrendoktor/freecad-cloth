"""Real-FreeCAD smoke coverage for public staged sewing Preview/Commit/Cancel."""
from pathlib import Path
import math
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part
import InitGui

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternObjects import add_pattern_piece
from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece
from freecad_cloth.sewing.SewingCommands import get_active_staged_sewing_task_panel


LOG_PATH = Path(os.environ.get("CLOTH_SEWING_SMOKE_LOG", ROOT / "artifacts" / "sewing-creation-smoke.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG = []
LOG_PATH.write_text("", encoding="utf-8")


def set_native_bezier_boundary(sketch, piece_id, span, height):
    p0 = App.Vector(0, 0, 0)
    p1 = App.Vector(span, 0, 0)
    p2 = App.Vector(span, 40, 0)
    p3 = App.Vector(0, 40, 0)
    curve = Part.BezierCurve()
    curve.setPoles([
        p2,
        App.Vector(span * 1.35, 40 + height, 0),
        App.Vector(-span * 0.35, 40 + height, 0),
        p3,
    ])
    sketch.clear()
    sketch.addGeometry([
        Part.LineSegment(p0, p1),
        Part.LineSegment(p1, p2),
        curve,
        Part.LineSegment(p3, p0),
    ], False)
    sketch.SemanticEdgeIds = [f"{piece_id}:edge:{i}" for i in range(4)]
    sketch.GeometryAuthority = "Sketcher"


def edge_sample_spacing(edge, fractions=(0.0, 0.07, 0.19, 0.43, 0.71, 1.0)):
    first = float(edge.FirstParameter)
    last = float(edge.LastParameter)
    points = [
        edge.valueAt(first + (last - first) * float(fraction))
        for fraction in fractions
    ]
    return [
        ((right.x - left.x) ** 2 + (right.y - left.y) ** 2 + (right.z - left.z) ** 2) ** 0.5
        for left, right in zip(points, points[1:])
    ]


def process_events():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def record(message):
    LOG.append(message)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()
    print(message, flush=True)


def wait_for_task_close():
    for _ in range(80):
        process_events()
        active = Gui.Control.activeDialog()
        if active is None or not bool(active):
            return
    raise AssertionError("task dialog did not close after the requested Commit/Cancel action")


def select_object(obj):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(obj)
    process_events()


def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def open_public(command):
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()
    Gui.runCommand(command, 0)
    process_events()
    panel = get_active_staged_sewing_task_panel()
    assert panel is not None, command + " did not retain a task panel"
    assert getattr(panel, "form", None) is not None
    active = Gui.Control.activeDialog()
    assert active is not None, command + " did not open an active task dialog"
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    widgets = [panel.form] + list(panel.form.findChildren(QtWidgets.QWidget))
    dialog_text = " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )
    for required in ("Preview", "Commit", "Cancel", "Selected semantic pattern edges"):
        assert required in dialog_text, command + " task panel is missing required control text: " + required
    return panel


def close_public_task(panel=None):
    if panel is not None:
        try:
            panel.reject()
        except Exception:
            pass
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()


doc = None
_success = False
try:
    record("smoke=started")
    InitGui.ClothSewingWorkbench()
    record("workbench=initialized")
    Gui.activateWorkbench("ClothSewingWorkbench")
    process_events()
    for command in ("ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_FreeSewing"):
        assert command in Gui.listCommands(), "missing public sewing command: " + command
    record("commands=registered")

    doc = App.newDocument("SewingCreationSmoke")
    piece_a = add_pattern_piece(
        doc,
        PatternPiece("SmokeA", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-a"),
    )
    piece_b = add_pattern_piece(
        doc,
        PatternPiece("SmokeB", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-b"),
    )
    piece_c = add_pattern_piece(
        doc,
        PatternPiece("SmokeC", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-c"),
    )
    doc.recompute()
    record("fixtures=created pieces=3")

    before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 0))
    panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in panel.session.created), "1:1 preview did not create a seam"
    assert "Preview valid" in panel.feedback.text()
    assert Gui.Control.activeDialog() is not None
    record("preview-1to1=passed")
    panel.commit_button.click()
    process_events()
    wait_for_task_close()
    assert any(
        getattr(obj, "SeamId", "") for obj in doc.Objects if obj.Name not in before
    ), "1:1 commit lost seam"
    record("commit-1to1=passed")

    cancel_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 1), (piece_b, 1))
    cancel_panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in cancel_panel.session.created)
    cancel_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == cancel_before, "cancel persisted preview objects"
    record("cancel-1to1=passed")

    count_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 2))
    invalid_count_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_count_panel.feedback.text()
    assert "exactly two edges" in invalid_count_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == count_before
    invalid_count_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == count_before
    record("selection-count-rejection=passed")

    same_piece_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_a, 1))
    invalid_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_panel.feedback.text()
    assert "different pattern pieces" in invalid_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    invalid_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    record("invalid-same-piece-preview=passed")

    mn_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 1), (piece_c, 2))
    invalid_mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert "Preview rejected" in invalid_mn_panel.feedback.text()
    assert "two different pattern pieces" in invalid_mn_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == mn_before
    invalid_mn_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == mn_before
    record("invalid-mn-partition-preview=passed")

    select_edges((piece_a, 0), (piece_a, 1), (piece_b, 0), (piece_b, 1))
    mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert any(
        getattr(obj, "SewingType", "") == "SewingNetwork"
        for obj in mn_panel.session.created
    )
    assert "Preview valid" in mn_panel.feedback.text()
    record("preview-mn=passed")
    mn_panel.commit_button.click()
    wait_for_task_close()
    networks = [
        obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"
    ]
    assert networks and networks[-1].Status == "Valid", "M:N commit did not leave a valid network"
    record("commit-mn=passed")

    # Use the existing canonical PatternPiece + Sketcher path for a real curved M:N relationship.
    curved_a = add_pattern_piece(
        doc,
        PatternPiece("CurvedA", [(0, 0), (100, 0), (100, 40), (0, 40)], id="curved-a"),
    )
    curved_b = add_pattern_piece(
        doc,
        PatternPiece("CurvedB", [(0, 0), (160, 0), (160, 40), (0, 40)], id="curved-b"),
    )
    curved_sketch_a = create_sketch_for_piece(
        PatternPiece("CurvedA", [(0, 0), (100, 0), (100, 40), (0, 40)], id="curved-a"),
        doc,
    )
    curved_sketch_b = create_sketch_for_piece(
        PatternPiece("CurvedB", [(0, 0), (160, 0), (160, 40), (0, 40)], id="curved-b"),
        doc,
    )
    set_native_bezier_boundary(curved_sketch_a, "curved-a", 100.0, 80.0)
    set_native_bezier_boundary(curved_sketch_b, "curved-b", 160.0, 10.0)
    doc.recompute()

    assert str(getattr(curved_a, "GeometryAuthority", "")) == "Sketcher"
    assert str(type(curved_sketch_a.Geometry[2]).__name__).lower() == "beziercurve"
    from freecad_cloth.pattern.PatternIR import PatternIR
    from freecad_cloth.sewing.SeamGraph import SeamGraph
    graph = SeamGraph()
    graph.add_piece(PatternPiece("CurvedA", [(0, 0), (100, 0), (100, 40), (0, 40)], id="curved-a"))
    graph.add_piece(PatternPiece("CurvedB", [(0, 0), (160, 0), (160, 40), (0, 40)], id="curved-b"))
    ir_a = PatternIR.from_sketches(graph, {"curved-a": curved_sketch_a, "curved-b": curved_sketch_b}, curve_samples=32)
    assert ir_a.boundary("curved-a", "curved-a:edge:2").kind == "bezier"
    record("curved-native-sketch=passed kind=bezier")

    curve_spacings = edge_sample_spacing(curved_a.Shape.Edges[2])
    assert max(curve_spacings) / min(curve_spacings) > 1.20
    record("curved-sampling=passed max_spacing=%.6f min_spacing=%.6f" % (max(curve_spacings), min(curve_spacings)))

    select_edges((curved_a, 0), (curved_a, 2), (curved_b, 0), (curved_b, 2))
    curved_panel = open_public("ClothSewing_CreateMNSewing")
    curved_preview = next(
        obj for obj in curved_panel.session.created
        if getattr(obj, "SewingType", "") == "SewingNetwork"
    )
    assert curved_preview.SideACount == 2
    assert curved_preview.SideBCount == 2
    assert len(curved_preview.Seams) == 3
    assert curved_preview.Status == "Valid"
    curved_relationship_id = str(curved_preview.RelationshipId)
    curved_panel.commit_button.click()
    wait_for_task_close()
    doc.recompute()
    curved_network = next(
        obj for obj in doc.Objects
        if getattr(obj, "SewingType", "") == "SewingNetwork"
        and str(getattr(obj, "RelationshipId", "")) == curved_relationship_id
    )

    from freecad_cloth.sewing.SewingObjects import _seam_length
    side_a_total = sum(float(_seam_length(curved_a, seam, "A")) for seam in curved_network.Seams)
    side_b_total = sum(float(_seam_length(curved_b, seam, "B")) for seam in curved_network.Seams)
    assert abs(side_a_total - float(curved_network.LengthA)) < 1e-6
    assert abs(side_b_total - float(curved_network.LengthB)) < 1e-6
    assert abs(float(curved_network.LengthA) - float(curved_network.LengthB)) / min(
        float(curved_network.LengthA), float(curved_network.LengthB)
    ) < 0.05
    assert any(
        float(seam.EndB) < 0.99 and float(seam.EndA) > 0.99
        for seam in curved_network.Seams
    )
    record("curved-mn=passed members=2,2 segments=3 physical-length=proportional")

    from freecad_cloth.sewing.SewingCorrespondence import map_parameter
    before_ranges = tuple(
        (float(seam.StartB), float(seam.EndB)) for seam in curved_network.Seams
    )
    for seam in curved_network.Seams:
        select_object(seam)
        Gui.runCommand("ClothSewing_ReverseSeam", 0)
        process_events()
        assert bool(seam.ReversedB)
        assert map_parameter(0.0, reversed_b=True) == 1.0
    assert before_ranges == tuple(
        (float(seam.StartB), float(seam.EndB)) for seam in curved_network.Seams
    )
    assert curved_network.Status == "Valid"
    record("curved-mn-reversal=passed segments=3")

    visual_seam = curved_network.Seams[0]
    assert not visual_seam.Shape.isNull()
    assert len(visual_seam.Shape.Edges) >= 15
    select_object(visual_seam)
    from freecad_cloth.sewing.SewingObjects import _edge_samples, _resolved_edge
    from freecad_cloth.sewing.SewingView import seam_visual_markers
    pts_a = _edge_samples(
        curved_a,
        _resolved_edge(curved_a, visual_seam, "A"),
        visual_seam.StartA,
        visual_seam.EndA,
        5,
    )
    pts_b = _edge_samples(
        curved_b,
        _resolved_edge(curved_b, visual_seam, "B"),
        visual_seam.StartB,
        visual_seam.EndB,
        5,
    )
    if visual_seam.ReversedB:
        pts_b.reverse()
    markers = seam_visual_markers(
        tuple((p.x, p.y, p.z) for p in pts_a),
        tuple((p.x, p.y, p.z) for p in pts_b),
    )
    assert len(markers["correspondence"]) == 5
    assert len(markers["direction_A"]) == 2
    assert len(markers["direction_B"]) == 2
    assert len(markers["notch_A"]) == 2
    assert len(markers["notch_B"]) == 2
    record("seam-visual-3d=passed edges=%d correspondence=5 direction=2 notch=2" % len(visual_seam.Shape.Edges))

    Gui.runCommand("ClothSewing_Show2D", 0)
    process_events()
    assert bool(getattr(visual_seam.ViewObject, "Visibility", True))
    record("seam-visual-2d=passed top-view=true")

    import tempfile
    save_fd, save_path = tempfile.mkstemp(suffix=".FCStd")
    os.close(save_fd)
    try:
        doc.saveAs(save_path)
        App.closeDocument(doc.Name)
        doc = None
        reloaded = App.openDocument(save_path)
        reloaded.recompute()
        curved_network = next(
            obj for obj in reloaded.Objects
            if getattr(obj, "SewingType", "") == "SewingNetwork"
            and str(getattr(obj, "RelationshipId", "")) == curved_relationship_id
        )
        assert curved_network.Status == "Valid"
        assert all(str(seam.Status) == "Valid" for seam in curved_network.Seams)
        record("curved-mn-save-reload=passed status=Valid")

        restored_a = next(obj for obj in reloaded.Objects if getattr(obj, "PieceId", "") == "curved-a")
        restored_sketch = restored_a.Sketch
        set_native_bezier_boundary(restored_sketch, "curved-a", 100.0, 120.0)
        reloaded.recompute()

        changed = [seam for seam in curved_network.Seams if str(seam.Status) == "Changed reference"]
        assert len(changed) == 1
        assert str(curved_network.Status) == "Invalid"
        assert "Changed reference" in str(curved_network.InvalidReason)
        record("curved-mn-invalidation=passed changed=%d network=%s" % (len(changed), curved_network.Status))

        changed_seam = changed[0]
        select_object(changed_seam)
        Gui.runCommand("ClothSewing_RepairSeam", 0)
        process_events()
        reloaded.recompute()
        assert all(str(seam.Status) == "Valid" for seam in curved_network.Seams)
        assert curved_network.Status == "Valid"
        assert str(changed_seam.EdgeAId) == "curved-a:edge:2"
        record("curved-mn-explicit-repair=passed status=Valid")
    finally:
        try:
            os.unlink(save_path)
        except OSError:
            pass

    select_edges((piece_a, 3), (piece_b, 3))
    free_panel = open_public("ClothSewing_FreeSewing")
    assert any(getattr(obj, "SewingType", "") == "SewingNetwork" for obj in free_panel.session.created)
    assert "Preview valid" in free_panel.feedback.text()
    record("preview-free=passed")
    free_panel.commit_button.click()
    wait_for_task_close()
    free_networks = [
        obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"
    ]
    assert any(len(network.Seams) == 1 and network.Status == "Valid" for network in free_networks)
    record("commit-free=passed")

    free_cancel_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 2), (piece_b, 2))
    free_cancel_panel = open_public("ClothSewing_FreeSewing")
    assert free_cancel_panel.session.created
    assert "Preview valid" in free_cancel_panel.feedback.text()
    free_cancel_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == free_cancel_before
    record("cancel-free=passed")


    _success = True
except Exception:
    record("smoke=exception\n" + traceback.format_exc())
    raise
finally:
    LOG.append("sewing-creation-smoke=completed")
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print("sewing-creation-smoke=completed", flush=True)

if _success:
    sys.stdout.flush()
    getattr(os, "_" + "exit")(0)

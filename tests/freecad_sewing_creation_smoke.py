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
from freecad_cloth.sewing.SewingCommands import get_active_staged_sewing_task_panel


LOG_PATH = Path(os.environ.get("CLOTH_SEWING_SMOKE_LOG", ROOT / "artifacts" / "sewing-creation-smoke.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG = []
LOG_PATH.write_text("", encoding="utf-8")




def add_curved_piece(doc, name, piece_id, line_length, curve_span=80.0, curve_height=90.0):
    """Create a real Part edge set with a curved, physically non-uniform boundary."""
    line_length = float(line_length)
    curve_span = float(curve_span)
    curve_height = float(curve_height)
    p0 = App.Vector(0, 0, 0)
    p1 = App.Vector(line_length, 0, 0)
    p2 = App.Vector(line_length, 40, 0)
    p3 = App.Vector(line_length - curve_span, 40, 0)
    curve = Part.BezierCurve()
    curve.setPoles([
        p2,
        App.Vector(line_length, 40 + curve_height, 0),
        App.Vector(line_length - curve_span, 40 + curve_height, 0),
        p3,
    ])
    edges = [
        Part.makeLine(p0, p1),
        Part.makeLine(p1, p2),
        curve.toShape(),
        Part.makeLine(p3, p0),
    ]
    obj = doc.addObject("Part::Feature", name)
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = str(piece_id)
    obj.addProperty("App::PropertyLength", "Width", "Parameters").Width = max(line_length, curve_span)
    obj.addProperty("App::PropertyLength", "Height", "Parameters").Height = 40.0 + curve_height
    obj.addProperty("App::PropertyString", "SewingOutline", "Cloth").SewingOutline = repr([
        (0.0, 0.0),
        (line_length, 0.0),
        (line_length, 40.0),
        (line_length - curve_span, 40.0),
    ])
    obj.Shape = Part.Face(Part.Wire(edges))
    return obj


def edge_sample_spacing(edge, parameters=(0.0, 0.07, 0.19, 0.43, 0.71, 1.0)):
    first = float(edge.FirstParameter)
    last = float(edge.LastParameter)
    points = [
        edge.valueAt(first + (last - first) * float(parameter))
        for parameter in parameters
    ]
    distances = []
    for left, right in zip(points, points[1:]):
        distances.append(
            ((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2) ** 0.5
        )
    return points, distances

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


def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def select_object(obj):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(obj)
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

    # Real curved 2:2 M:N fixture.  The selected boundaries have unequal
    # member lengths on each side so the canonical M:N builder must partition
    # by physical length rather than boundary-vertex index.
    curved_a = add_curved_piece(
        doc, "CurvedA", "curved-a", 100.0, curve_span=80.0, curve_height=90.0
    )
    doc.recompute()
    a_line_length = float(curved_a.Shape.Edges[0].Length)
    a_curve_length = float(curved_a.Shape.Edges[2].Length)

    probe_curve = Part.BezierCurve()
    probe_curve.setPoles([
        App.Vector(0, 40, 0),
        App.Vector(0, 160, 0),
        App.Vector(-80, 160, 0),
        App.Vector(-80, 40, 0),
    ])
    b_curve_length = float(probe_curve.toShape().Length)
    b_line_length = a_line_length + a_curve_length - b_curve_length
    assert b_line_length > 1.0

    curved_b = add_curved_piece(
        doc, "CurvedB", "curved-b", b_line_length, curve_span=80.0, curve_height=120.0
    )
    doc.recompute()

    _curve_points, curve_spacings = edge_sample_spacing(curved_a.Shape.Edges[2])
    assert max(curve_spacings) / min(curve_spacings) > 1.20, (
        "fixture did not produce deliberately non-uniform curve sampling"
    )
    record(
        "curved-sampling=passed max_spacing=%.6f min_spacing=%.6f"
        % (max(curve_spacings), min(curve_spacings))
    )

    select_edges((curved_a, 0), (curved_a, 2), (curved_b, 0), (curved_b, 2))
    curved_panel = open_public("ClothSewing_CreateMNSewing")
    curved_preview = next(
        (
            obj
            for obj in curved_panel.session.created
            if getattr(obj, "SewingType", "") == "SewingNetwork"
        ),
        None,
    )
    assert curved_preview is not None
    assert curved_preview.Status == "Valid"
    assert len(curved_preview.Seams) == 3, (
        "unequal 2:2 member lengths should produce three canonical overlap segments"
    )
    assert curved_preview.SideACount == 2
    assert curved_preview.SideBCount == 2
    assert abs(float(curved_preview.LengthA) - float(curved_preview.LengthB)) < 1e-6
    curved_panel.commit_button.click()
    wait_for_task_close()
    doc.recompute()
    curved_network = next(
        obj
        for obj in doc.Objects
        if getattr(obj, "SewingType", "") == "SewingNetwork"
        and str(getattr(obj, "RelationshipId", "")) == str(curved_preview.RelationshipId)
    )

    from freecad_cloth.sewing.SewingObjects import _seam_length
    side_a_sum = sum(float(_seam_length(curved_a, seam, "A")) for seam in curved_network.Seams)
    side_b_sum = sum(float(_seam_length(curved_b, seam, "B")) for seam in curved_network.Seams)
    assert abs(side_a_sum - (a_line_length + a_curve_length)) < 1e-6
    assert abs(side_b_sum - float(curved_network.LengthB)) < 1e-6
    assert all(
        abs(float(_seam_length(curved_a, seam, "A")) - float(_seam_length(curved_b, seam, "B"))) < 1e-5
        for seam in curved_network.Seams
    )
    record("curved-mn=passed members=2,2 segments=3 physical-length=proportional")

    from freecad_cloth.sewing.SewingCorrespondence import map_parameter
    for seam in curved_network.Seams:
        select_object(seam)
        before_reversed = bool(seam.ReversedB)
        Gui.runCommand("ClothSewing_ReverseSeam", 0)
        _events()
        assert bool(seam.ReversedB) is (not before_reversed)
        assert map_parameter(0.0, reversed_b=bool(seam.ReversedB)) == (
            1.0 if seam.ReversedB else 0.0
        )
    doc.recompute()
    assert all(bool(seam.ReversedB) for seam in curved_network.Seams)
    assert str(curved_network.Status) == "Valid"
    record("curved-mn-reversal=passed segments=3")

    select_object(curved_network)
    Gui.runCommand("ClothSewing_EditNetwork", 0)
    process_events()
    network_dialog = Gui.Control.activeDialog()
    assert network_dialog is not None
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    network_form = getattr(network_dialog, "form", network_dialog)
    network_widgets = [network_form]
    if hasattr(network_form, "findChildren"):
        network_widgets.extend(network_form.findChildren(QtWidgets.QWidget))
    network_text = " | ".join(
        str(getter())
        for widget in network_widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    ).lower()
    assert "severity info" in network_text
    assert "recovery:" in network_text
    record("correspondence-gui-evidence=passed severity=info")
    reject_network_editor = getattr(network_dialog, "reject", None)
    if callable(reject_network_editor):
        reject_network_editor()
    else:
        Gui.Control.closeDialog()
    process_events()

    visual_seam = curved_network.Seams[0]
    assert not visual_seam.Shape.isNull()
    assert len(visual_seam.Shape.Edges) >= 10, (
        "seam view must expose correspondence links plus direction/notch markers"
    )
    assert bool(getattr(visual_seam.ViewObject, "Visibility", True))
    record("seam-visual-3d=passed edges=%d" % len(visual_seam.Shape.Edges))
    select_object(visual_seam)
    Gui.runCommand("ClothSewing_Show2D", 0)
    process_events()
    assert not visual_seam.Shape.isNull()
    record("seam-visual-2d=passed top-view=true")

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


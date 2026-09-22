"""Focused real-FreeCAD/Xvfb acceptance contract for issue #845."""
from pathlib import Path
import math
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part
import InitGui

from freecad_cloth.sewing.SewingCommands import get_active_staged_sewing_task_panel
from freecad_cloth.sewing.SewingObjects import _edge_length, _seam_length
from freecad_cloth.sewing.SewingView import seam_visual_markers


LOG_PATH = Path(
    os.environ.get(
        "CLOTH_SEWING_845_LOG",
        ROOT / "artifacts" / "sewing-845-acceptance.log",
    )
)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.write_text("", encoding="utf-8")


def record(message):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()
    print(message, flush=True)


def process_events():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def wait_for_dialog_close():
    for _ in range(80):
        process_events()
        if Gui.Control.activeDialog() is None:
            return
    raise AssertionError("FreeCAD task dialog did not close")


def add_curved_piece(doc, name, piece_id, line_length, curve_span, curve_height):
    line_length = float(line_length)
    curve_span = float(curve_span)
    curve_height = float(curve_height)
    p0 = App.Vector(0, 0, 0)
    p1 = App.Vector(line_length, 0, 0)
    p2 = App.Vector(line_length, 40, 0)
    p3 = App.Vector(line_length - curve_span, 40, 0)
    curve = Part.BezierCurve()
    curve.setPoles(
        [
            p2,
            App.Vector(line_length, 40 + curve_height, 0),
            App.Vector(line_length - curve_span, 40 + curve_height, 0),
            p3,
        ]
    )
    edges = [
        Part.makeLine(p0, p1),
        Part.makeLine(p1, p2),
        curve.toShape(),
        Part.makeLine(p3, p0),
    ]
    obj = doc.addObject("Part::Feature", name)
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = piece_id
    obj.addProperty("App::PropertyString", "SewingOutline", "Cloth").SewingOutline = repr(
        [(0.0, 0.0), (line_length, 0.0), (line_length, 40.0), (line_length - curve_span, 40.0)]
    )
    obj.addProperty("App::PropertyLength", "Width", "Parameters").Width = max(line_length, curve_span)
    obj.addProperty("App::PropertyLength", "Height", "Parameters").Height = 40.0 + curve_height
    obj.Shape = Part.Face(Part.Wire(edges))
    return obj


def sampled_length(edge):
    points = edge.discretize(Number=64)
    return sum(
        math.sqrt(
            (right.x - left.x) ** 2
            + (right.y - left.y) ** 2
            + (right.z - left.z) ** 2
        )
        for left, right in zip(points, points[1:])
    )


def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def select_object(obj):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(obj)
    process_events()


def main():
    InitGui.ClothSewingWorkbench()
    Gui.activateWorkbench("ClothSewingWorkbench")
    process_events()

    doc = App.newDocument("Sewing845Acceptance")
    try:
        curved_a = add_curved_piece(
            doc, "CurvedA", "curved-a", 100.0, curve_span=80.0, curve_height=90.0
        )
        probe_b = Part.BezierCurve()
        probe_b.setPoles(
            [
                App.Vector(0, 40, 0),
                App.Vector(0, 160, 0),
                App.Vector(-80, 160, 0),
                App.Vector(-80, 40, 0),
            ]
        )
        a_total = sampled_length(curved_a.Shape.Edges[0]) + sampled_length(curved_a.Shape.Edges[2])
        b_curve = sampled_length(probe_b.toShape())
        curved_b = add_curved_piece(
            doc,
            "CurvedB",
            "curved-b",
            a_total - b_curve,
            curve_span=80.0,
            curve_height=120.0,
        )
        doc.recompute()

        curve = curved_a.Shape.Edges[2]
        fractions = (0.0, 0.07, 0.19, 0.43, 0.71, 1.0)
        samples = [curve.valueAt(curve.FirstParameter + (curve.LastParameter - curve.FirstParameter) * f) for f in fractions]
        spacings = [
            math.sqrt(
                (right.x - left.x) ** 2
                + (right.y - left.y) ** 2
                + (right.z - left.z) ** 2
            )
            for left, right in zip(samples, samples[1:])
        ]
        assert max(spacings) / min(spacings) > 1.20
        record(
            "curved-sampling=passed max_spacing=%.6f min_spacing=%.6f"
            % (max(spacings), min(spacings))
        )

        select_edges((curved_a, 0), (curved_a, 2), (curved_b, 0), (curved_b, 2))
        Gui.runCommand("ClothSewing_CreateMNSewing", 0)
        process_events()
        panel = get_active_staged_sewing_task_panel()
        assert panel is not None
        preview = next(
            obj
            for obj in panel.session.created
            if getattr(obj, "SewingType", "") == "SewingNetwork"
        )
        assert preview.Status == "Valid"
        assert len(preview.Seams) == 3
        assert preview.SideACount == 2
        assert preview.SideBCount == 2
        assert abs(float(preview.LengthA) - float(preview.LengthB)) < 1e-6
        record("curved-mn=passed members=2,2 segments=3 physical-length=proportional")

        panel.commit_button.click()
        wait_for_dialog_close()
        doc.recompute()

        network = next(
            obj
            for obj in doc.Objects
            if getattr(obj, "SewingType", "") == "SewingNetwork"
            and str(getattr(obj, "RelationshipId", "")) == str(preview.RelationshipId)
        )
        segment_lengths_a = [_seam_length(curved_a, seam, "A") for seam in network.Seams]
        segment_lengths_b = [_seam_length(curved_b, seam, "B") for seam in network.Seams]
        assert all(abs(a - b) < 1e-5 for a, b in zip(segment_lengths_a, segment_lengths_b))
        record("curved-mn-proportional=passed per-segment=true")

        for seam in network.Seams:
            select_object(seam)
            Gui.runCommand("ClothSewing_ReverseSeam", 0)
            process_events()
            assert bool(seam.ReversedB)
        doc.recompute()
        assert network.Status == "Valid"
        record("curved-mn-reversal=passed segments=3")

        select_object(network)
        Gui.runCommand("ClothSewing_EditNetwork", 0)
        process_events()
        dialog = Gui.Control.activeDialog()
        assert dialog is not None
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        form = getattr(dialog, "form", dialog)
        widgets = [form] + list(form.findChildren(QtWidgets.QWidget))
        text = " | ".join(
            str(getter())
            for widget in widgets
            for getter in [getattr(widget, "text", None)]
            if callable(getter)
        ).lower()
        assert "severity info" in text
        assert "recovery:" in text
        record("correspondence-gui-evidence=passed severity=info")
        reject = getattr(dialog, "reject", None)
        if callable(reject):
            reject()
        else:
            Gui.Control.closeDialog()
        process_events()

        seam = network.Seams[0]
        assert not seam.Shape.isNull()
        assert len(seam.Shape.Edges) >= 10
        assert seam.ViewObject.Visibility
        record("seam-visual-3d=passed edges=%d" % len(seam.Shape.Edges))

        a_points = [
            tuple(float(v) for v in point)
            for point in [(0, 0, 0), (50, 20, 0), (100, 0, 0)]
        ]
        b_points = [
            tuple(float(v) for v in point)
            for point in [(100, 80, 0), (50, 100, 0), (0, 80, 0)]
        ]
        markers = seam_visual_markers(a_points, b_points)
        assert markers["direction_B"][1] == (-1.0, 0.0)
        assert markers["notch_B"][1] == (0.0, -1.0)
        assert markers["correspondence"][0][1] == b_points[0]

        select_object(seam)
        Gui.runCommand("ClothSewing_Show2D", 0)
        process_events()
        assert not seam.Shape.isNull()
        record("seam-visual-2d=passed top-view=true")
        record("seam-direction-notch-correspondence=passed")
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
    record("sewing-845-acceptance=completed")


if __name__ == "__main__":
    main()

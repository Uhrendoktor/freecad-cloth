"""Real-FreeCAD smoke coverage for the public production SVG/DXF export."""
from pathlib import Path
import os
import tempfile
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import InitGui

from freecad_cloth.pattern.PatternExport import from_dxf_metadata, from_svg_metadata
from freecad_cloth.pattern.PatternCommands import get_active_pattern_export_task_panel

LOG_PATH = Path(os.environ.get("CLOTH_PATTERN_EXPORT_LOG", ROOT / "artifacts" / "pattern-production-export.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG = []
LOG_PATH.write_text("", encoding="utf-8")


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


def open_public_export(piece):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    process_events()
    Gui.runCommand("ClothPattern_Export", 0)
    process_events()
    panel = get_active_pattern_export_task_panel()
    if panel is None or getattr(panel, "form", None) is None:
        raise RuntimeError("public Pattern export command did not retain its task panel")
    if not panel.form.isVisible():
        raise RuntimeError("public Pattern export task panel is not visible")
    if Gui.Control.activeDialog() is None:
        raise RuntimeError("public Pattern export command did not open a task dialog")
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


def accept_public_task(panel, export_format):
    try:
        accepted = panel.accept()
    except Exception as exc:
        raise RuntimeError(
            "public export task panel could not accept %s: %s" % (export_format, exc)
        ) from exc
    if accepted is False:
        raise RuntimeError("public export task panel rejected %s export" % export_format)
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()
    for _ in range(80):
        active = Gui.Control.activeDialog()
        if active is None or not bool(active):
            return
        process_events()
    raise RuntimeError(
        "public export task panel did not close after successful %s" % export_format
    )


doc = None
try:
    record("smoke=started")
    InitGui.ClothPatternWorkbench()
    record("workbench=initialized")
    Gui.activateWorkbench("ClothPatternWorkbench")
    process_events()

    for command in ("ClothPattern_CreatePieceWithSketch", "ClothPattern_EditSketch", "ClothPattern_Export"):
        if command not in Gui.listCommands():
            raise RuntimeError("missing public Pattern command: " + command)
    if "ClothPattern_CreateDrafting" in Gui.listCommands():
        raise RuntimeError("legacy PatternDrafting command leaked into the public workbench surface")
    record("commands=registered sketcher-only")

    doc = App.newDocument("PatternProductionExportSmoke")
    record("document=created")
    Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
    process_events()
    record("piece-create=completed")
    piece = next(
        (obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"),
        None,
    )
    if piece is None:
        raise RuntimeError("public Pattern command did not create a PatternPiece")
    doc.recompute()
    record("piece=ready")
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()
    for _ in range(40):
        active = Gui.Control.activeDialog()
        if active is None or not bool(active):
            break
        process_events()
    else:
        raise RuntimeError("pattern creation task panel remained open before export")

    with tempfile.TemporaryDirectory() as directory:
        output_dir = Path(directory)
        document_path = output_dir / "pattern-roundtrip.FCStd"

        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        process_events()
        doc.recompute()
        pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
        if len(pieces) != 2:
            raise RuntimeError("real-FreeCAD export smoke did not create two native Sketch PatternPieces")
        piece = pieces[0]
        other_piece = pieces[1]
        if str(getattr(piece, "GeometryAuthority", "")) != "Sketcher" or str(getattr(other_piece, "GeometryAuthority", "")) != "Sketcher":
            raise RuntimeError("export smoke pieces are not native Sketch-authoritative PatternPieces")

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(piece)
        process_events()
        Gui.runCommand("ClothPattern_AddNotch", 0)
        process_events()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(piece)
        process_events()
        Gui.runCommand("ClothPattern_AddInternalMark", 0)
        process_events()
        Gui.runCommand("ClothPattern_AddSeam", 0)
        process_events()
        doc.recompute()

        pre_save_seams = [obj for obj in doc.Objects if str(getattr(obj, "SeamId", "")).strip()]
        pre_save_marks = [obj for obj in doc.Objects if str(getattr(obj, "PatternMarkType", "")).strip() and str(getattr(obj, "PieceId", "")).strip() == str(piece.PieceId)]
        if len(pre_save_seams) != 1 or len(pre_save_marks) != 2:
            raise RuntimeError("export smoke did not persist the expected seam/notch/mark objects")
        seam_id = str(pre_save_seams[0].SeamId)
        notch = next(obj for obj in pre_save_marks if str(obj.PatternMarkType) == "Notch")
        construction_mark = next(obj for obj in pre_save_marks if str(obj.PatternMarkType) == "InternalMark")
        piece_id = str(piece.PieceId)
        notch_id = str(getattr(notch, "PatternMarkId", notch.Name))
        mark_id = str(getattr(construction_mark, "PatternMarkId", construction_mark.Name))
        if str(getattr(notch, "SegmentId", "")) != piece_id + ":edge:0":
            raise RuntimeError("notch did not persist its semantic native edge reference")
        if str(getattr(construction_mark, "SegmentId", "")) != piece_id + ":edge:0":
            raise RuntimeError("construction mark did not persist its semantic native edge reference")
        if str(getattr(pre_save_seams[0], "Status", "")) != "Valid":
            raise RuntimeError("persisted seam is not valid before export round-trip")

        doc.saveAs(str(document_path))
        saved_name = doc.Name
        App.closeDocument(saved_name)
        process_events()
        doc = App.openDocument(str(document_path))
        process_events()
        doc.recompute()

        piece = next((obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece" and str(getattr(obj, "PieceId", "")) == piece_id), None)
        if piece is None:
            raise RuntimeError("save/reload lost the selected native Sketch PatternPiece identity")
        if str(getattr(piece, "GeometryAuthority", "")) != "Sketcher" or getattr(piece, "Sketch", None) is None:
            raise RuntimeError("save/reload lost the native Sketch authority")
        if list(getattr(piece.Sketch, "SemanticEdgeIds", ())) != [piece_id + ":edge:%d" % index for index in range(4)]:
            raise RuntimeError("save/reload changed native semantic edge identities")
        seams = [obj for obj in doc.Objects if str(getattr(obj, "SeamId", "")).strip()]
        marks = [obj for obj in doc.Objects if str(getattr(obj, "PatternMarkType", "")).strip() and str(getattr(obj, "PieceId", "")).strip() == piece_id]
        if len(seams) != 1 or str(seams[0].SeamId) != seam_id or str(seams[0].Status) != "Valid":
            raise RuntimeError("save/reload lost seam identity or validity")
        notch = next((obj for obj in marks if str(obj.PatternMarkType) == "Notch" and str(getattr(obj, "PatternMarkId", "")) == notch_id), None)
        construction_mark = next((obj for obj in marks if str(obj.PatternMarkType) == "InternalMark" and str(getattr(obj, "PatternMarkId", "")) == mark_id), None)
        if notch is None or construction_mark is None:
            raise RuntimeError("save/reload lost construction mark identities")
        if (str(notch.SegmentId), float(notch.Position), float(notch.Depth)) != (piece_id + ":edge:0", 0.5, 3.0):
            raise RuntimeError("save/reload changed persisted notch geometry")
        if (str(construction_mark.SegmentId), float(construction_mark.Position), float(construction_mark.Angle), float(construction_mark.Length), str(construction_mark.Text)) != (piece_id + ":edge:0", 0.5, 0.0, 40.0, "Internal mark"):
            raise RuntimeError("save/reload changed persisted construction mark geometry")
        record("roundtrip=passed piece=%s seam=%s notch=%s mark=%s" % (piece_id, seam_id, notch_id, mark_id))

        source_before = (
            str(piece.Label),
            str(piece.PieceId),
            str(piece.SewingOutline),
            float(piece.SeamAllowance),
            float(piece.GrainlineAngle),
            str(getattr(piece, "GeometryAuthority", "")),
            tuple((str(obj.PatternMarkId), str(obj.PatternMarkType), str(obj.PieceId), str(obj.SegmentId), float(obj.Position), float(obj.Depth), float(obj.Angle), float(obj.Length), str(obj.Text)) for obj in sorted(marks, key=lambda value: str(getattr(value, "PatternMarkId", "")))),
            tuple((str(obj.SeamId), str(obj.PieceA), str(obj.PieceB), str(obj.EdgeAId), str(obj.EdgeBId), str(obj.Status)) for obj in seams),
        )

        results = {}
        readers = {"SVG": from_svg_metadata, "DXF": from_dxf_metadata}
        for export_format in ("SVG", "DXF"):
            path_a = output_dir / ("piece." + export_format.lower())
            path_b = output_dir / ("piece-second." + export_format.lower())

            panel = open_public_export(piece)
            record("export=%s:first-panel-opened" % export_format)
            panel.format.setCurrentText(export_format)
            panel.path.setText(str(path_a))
            record("export=%s:first-accept" % export_format)
            accept_public_task(panel, export_format)
            record("export=%s:first-written" % export_format)

            first = path_a.read_bytes()
            if not first:
                raise RuntimeError(export_format + " export is empty")

            panel = open_public_export(piece)
            record("export=%s:second-panel-opened" % export_format)
            panel.format.setCurrentText(export_format)
            panel.path.setText(str(path_b))
            record("export=%s:second-accept" % export_format)
            accept_public_task(panel, export_format)
            record("export=%s:second-written" % export_format)

            second = path_b.read_bytes()
            if first != second:
                raise RuntimeError(export_format + " export is not byte-deterministic")

            metadata = readers[export_format](first.decode("utf-8"))
            if metadata.get("piece_id") != str(piece.PieceId):
                raise RuntimeError(export_format + " export lost piece identity")
            if metadata.get("units") != "mm" or metadata.get("scale") != 1.0:
                raise RuntimeError(export_format + " export lost units/scale")
            if float(metadata.get("seam_allowance_mm", -1.0)) != float(piece.SeamAllowance):
                raise RuntimeError(export_format + " export lost seam allowance")
            if not metadata.get("edge_ids"):
                raise RuntimeError(export_format + " export lost semantic edge IDs")
            if not metadata.get("mark_ids"):
                raise RuntimeError(export_format + " export lost construction mark identity")
            results[export_format] = len(first)

        if source_before != (
            str(piece.Label),
            str(piece.PieceId),
            str(piece.SewingOutline),
            float(piece.SeamAllowance),
            float(piece.GrainlineAngle),
            str(getattr(piece, "GeometryAuthority", "")),
        ):
            raise RuntimeError("public export mutated authoritative PatternPiece state")

        record("pattern-export=passed formats=SVG,DXF bytes=%s,%s" % (results["SVG"], results["DXF"]))
except Exception:
    record("smoke=exception\n" + traceback.format_exc())
    raise
finally:
    LOG.append("pattern-export-smoke=completed")
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print("pattern-export-smoke=completed", flush=True)
    try:
        if App.ActiveDocument is not None and doc is not None and App.ActiveDocument.Name == doc.Name:
            App.closeDocument(doc.Name)
    except Exception:
        pass

# FreeCAD can retain a GUI event-loop/task-panel object after the script has finished.
# Force a clean process exit on the successful path, matching the existing real-GUI
# smoke-test convention without weakening any assertion above.
record("freecad-process-exit=forced")
sys.stdout.flush()
os._exit(0)

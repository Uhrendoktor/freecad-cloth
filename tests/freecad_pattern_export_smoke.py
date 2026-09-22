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
        pre_save_marks = [
            obj for obj in doc.Objects
            if str(getattr(obj, "PatternMarkType", "")).strip()
            and str(getattr(obj, "PieceId", "")).strip() == str(piece.PieceId)
        ]
        if len(pre_save_seams) != 1 or len(pre_save_marks) != 3:
            raise RuntimeError("export smoke did not persist the expected seam/notch/internal-mark/grainline objects")
        seam_id = str(pre_save_seams[0].SeamId)
        if str(getattr(pre_save_seams[0], "Status", "")) != "Valid":
            raise RuntimeError("persisted seam is not valid before export round-trip")
        mark_ids = {
            str(getattr(obj, "PatternMarkType", "")): str(getattr(obj, "PatternMarkId", obj.Name))
            for obj in pre_save_marks
        }
        if set(mark_ids) != {"Notch", "InternalMark", "Grainline"}:
            raise RuntimeError("export smoke did not persist all required construction-mark types")
        piece_id = str(piece.PieceId)

        doc.saveAs(str(document_path))
        saved_name = doc.Name
        App.closeDocument(saved_name)
        process_events()
        doc = App.openDocument(str(document_path))
        process_events()
        doc.recompute()

        piece = next(
            (obj for obj in doc.Objects
             if getattr(obj, "PatternType", "") == "PatternPiece"
             and str(getattr(obj, "PieceId", "")) == piece_id),
            None,
        )
        if piece is None or str(getattr(piece, "GeometryAuthority", "")) != "Sketcher" or getattr(piece, "Sketch", None) is None:
            raise RuntimeError("save/reload lost the selected native Sketch PatternPiece identity")
        expected_edge_ids = [piece_id + ":edge:%d" % index for index in range(4)]
        if list(getattr(piece.Sketch, "SemanticEdgeIds", ())) != expected_edge_ids:
            raise RuntimeError("save/reload changed native semantic edge identities")

        seams = [obj for obj in doc.Objects if str(getattr(obj, "SeamId", "")).strip()]
        marks = [
            obj for obj in doc.Objects
            if str(getattr(obj, "PatternMarkType", "")).strip()
            and str(getattr(obj, "PieceId", "")).strip() == piece_id
        ]
        if len(seams) != 1 or str(seams[0].SeamId) != seam_id or str(seams[0].Status) != "Valid":
            raise RuntimeError("save/reload lost seam identity or validity")
        persisted_types = {str(getattr(obj, "PatternMarkType", "")): obj for obj in marks}
        if set(persisted_types) != {"Notch", "InternalMark", "Grainline"}:
            raise RuntimeError("save/reload lost persisted construction-mark types")
        for mark_type, obj in persisted_types.items():
            if not str(getattr(obj, "PatternMarkId", "")).strip():
                raise RuntimeError("save/reload lost stable PatternMarkId for %s" % mark_type)
            if str(getattr(obj, "SegmentId", "")) != piece_id + ":edge:0":
                raise RuntimeError("save/reload changed semantic edge reference for %s" % mark_type)
        record("roundtrip=passed piece=%s seam=%s marks=%s" % (piece_id, seam_id, ",".join(sorted(persisted_types))))

        source_before = (
            str(piece.Label),
            str(piece.PieceId),
            str(piece.SewingOutline),
            float(piece.SeamAllowance),
            float(piece.GrainlineAngle),
            str(getattr(piece, "GeometryAuthority", "")),
            tuple(
                (
                    str(obj.PatternMarkId),
                    str(obj.PatternMarkType),
                    str(obj.PieceId),
                    str(obj.SegmentId),
                    float(obj.Position),
                    float(obj.Depth),
                    float(obj.Angle),
                    float(obj.Length),
                    str(obj.Text),
                )
                for obj in sorted(marks, key=lambda value: str(getattr(value, "PatternMarkId", "")))
            ),
            tuple(
                (
                    str(obj.SeamId),
                    str(obj.PieceA),
                    str(obj.PieceB),
                    str(obj.EdgeAId),
                    str(obj.EdgeBId),
                    str(obj.Status),
                )
                for obj in seams
            ),
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
            if metadata.get("piece_id") != piece_id:
                raise RuntimeError(export_format + " export lost piece identity")
            if metadata.get("units") != "mm" or metadata.get("scale") != 1.0:
                raise RuntimeError(export_format + " export lost units/scale")
            if float(metadata.get("seam_allowance_mm", -1.0)) != float(piece.SeamAllowance):
                raise RuntimeError(export_format + " export lost seam allowance")
            if not metadata.get("edge_ids"):
                raise RuntimeError(export_format + " export lost semantic edge IDs")
            if metadata.get("seam_ids") != [seam_id]:
                raise RuntimeError(export_format + " export lost persisted seam identity")
            if metadata.get("notch_ids") != [str(persisted_types["Notch"].PatternMarkId)]:
                raise RuntimeError(export_format + " export lost persisted notch identity")
            if metadata.get("mark_ids") != sorted(
                [str(persisted_types["Grainline"].PatternMarkId), str(persisted_types["InternalMark"].PatternMarkId)]
            ):
                raise RuntimeError(export_format + " export lost persisted construction-mark identity")
            output = first.decode("utf-8")
            if "Notch" not in output or "InternalMark" not in output or "Grainline" not in output:
                raise RuntimeError(export_format + " export lost persisted construction-mark geometry")
            results[export_format] = len(first)

        after_export = (
            str(piece.Label),
            str(piece.PieceId),
            str(piece.SewingOutline),
            float(piece.SeamAllowance),
            float(piece.GrainlineAngle),
            str(getattr(piece, "GeometryAuthority", "")),
            tuple(
                (
                    str(obj.PatternMarkId),
                    str(obj.PatternMarkType),
                    str(obj.PieceId),
                    str(obj.SegmentId),
                    float(obj.Position),
                    float(obj.Depth),
                    float(obj.Angle),
                    float(obj.Length),
                    str(obj.Text),
                )
                for obj in sorted(marks, key=lambda value: str(getattr(value, "PatternMarkId", "")))
            ),
            tuple(
                (
                    str(obj.SeamId),
                    str(obj.PieceA),
                    str(obj.PieceB),
                    str(obj.EdgeAId),
                    str(obj.EdgeBId),
                    str(obj.Status),
                )
                for obj in seams
            ),
        )
        if source_before != after_export:
            raise RuntimeError("public export mutated authoritative PatternPiece/seam/mark state")

        stale_path = output_dir / "stale.svg"
        persisted_types["Notch"].SegmentId = piece_id + ":edge:stale"
        doc.recompute()
        panel = open_public_export(piece)
        panel.format.setCurrentText("SVG")
        panel.path.setText(str(stale_path))
        accepted = panel.accept()
        if accepted is not False:
            close_public_task(panel)
            raise RuntimeError("public export accepted a stale construction-mark reference")
        if "blocked" not in panel.status.text().lower():
            close_public_task(panel)
            raise RuntimeError("public export did not report the stale-reference block")
        close_public_task(panel)
        if stale_path.exists():
            raise RuntimeError("stale semantic export wrote an artifact")
        record("stale-mark-guard=passed")

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

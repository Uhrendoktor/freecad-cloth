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

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(piece)
        process_events()
        Gui.runCommand("ClothPattern_AddNotch", 0)
        process_events()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(piece)
        process_events()
        Gui.runCommand("ClothPattern_AddGrainline", 0)
        process_events()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(piece)
        process_events()
        Gui.runCommand("ClothPattern_AddInternalMark", 0)
        process_events()
        doc.recompute()

        marks = [
            obj for obj in doc.Objects
            if str(getattr(obj, "PatternMarkType", "")).strip()
            and str(getattr(obj, "PieceId", "")).strip() == str(piece.PieceId)
        ]
        if len(marks) != 3:
            raise RuntimeError("export smoke did not persist notch, grainline, and internal mark objects")
        piece_id = str(piece.PieceId)
        notch = next(obj for obj in marks if str(obj.PatternMarkType) == "Notch")
        grainline = next(obj for obj in marks if str(obj.PatternMarkType) == "Grainline")
        construction_mark = next(obj for obj in marks if str(obj.PatternMarkType) == "InternalMark")
        notch_id = str(getattr(notch, "PatternMarkId", "")).strip()
        grainline_id = str(getattr(grainline, "PatternMarkId", "")).strip()
        mark_id = str(getattr(construction_mark, "PatternMarkId", "")).strip()
        if not all((notch_id, grainline_id, mark_id)):
            raise RuntimeError("native construction marks do not have persistent PatternMarkId values")
        edge_id = piece_id + ":edge:0"
        for obj in (notch, grainline, construction_mark):
            if str(getattr(obj, "SegmentId", "")) != edge_id:
                raise RuntimeError("native construction mark did not persist authored Sketch semantic edge identity")
        record(
            "marks=ready notch=%s grainline=%s internal=%s edge=%s"
            % (notch_id, grainline_id, mark_id, edge_id)
        )

        piece.SeamAllowance = 5.0
        doc.recompute()
        doc.saveAs(str(document_path))
        saved_name = doc.Name
        App.closeDocument(saved_name)
        process_events()
        doc = App.openDocument(str(document_path))
        process_events()
        doc.recompute()

        piece = next(
            (
                obj for obj in doc.Objects
                if getattr(obj, "PatternType", "") == "PatternPiece"
                and str(getattr(obj, "PieceId", "")) == piece_id
            ),
            None,
        )
        if piece is None:
            raise RuntimeError("save/reload lost the native PatternPiece identity")
        sketch = getattr(piece, "Sketch", None)
        if str(getattr(piece, "GeometryAuthority", "")) != "Sketcher" or sketch is None:
            raise RuntimeError("save/reload lost the native Sketch authority")
        if list(getattr(sketch, "SemanticEdgeIds", ())) != [
            piece_id + ":edge:%d" % index for index in range(4)
        ]:
            raise RuntimeError("save/reload changed authored Sketch semantic edge identities")

        marks = [
            obj for obj in doc.Objects
            if str(getattr(obj, "PatternMarkType", "")).strip()
            and str(getattr(obj, "PieceId", "")).strip() == piece_id
        ]
        notch = next(
            obj for obj in marks
            if str(obj.PatternMarkType) == "Notch"
            and str(getattr(obj, "PatternMarkId", "")) == notch_id
        )
        grainline = next(
            obj for obj in marks
            if str(obj.PatternMarkType) == "Grainline"
            and str(getattr(obj, "PatternMarkId", "")) == grainline_id
        )
        construction_mark = next(
            obj for obj in marks
            if str(obj.PatternMarkType) == "InternalMark"
            and str(getattr(obj, "PatternMarkId", "")) == mark_id
        )
        if str(notch.SegmentId) != edge_id or float(notch.Position) != 0.5 or float(notch.Depth) != 3.0:
            raise RuntimeError("save/reload changed persisted notch identity or geometry")
        if (
            str(grainline.SegmentId) != edge_id
            or float(grainline.Position) != 0.5
            or float(grainline.Angle) != 0.0
            or float(grainline.Length) != 36.0
        ):
            raise RuntimeError("save/reload changed persisted grainline identity or geometry")
        if (
            str(construction_mark.SegmentId) != edge_id
            or float(construction_mark.Position) != 0.5
            or float(construction_mark.Angle) != 0.0
            or float(construction_mark.Length) != 40.0
            or str(construction_mark.Text) != "Internal mark"
        ):
            raise RuntimeError("save/reload changed persisted construction-mark identity or geometry")
        record(
            "roundtrip=passed piece=%s notch=%s grainline=%s mark=%s"
            % (piece_id, notch_id, grainline_id, mark_id)
        )

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
            if metadata.get("notch_ids") != [notch_id]:
                raise RuntimeError(export_format + " export lost persisted notch identity")
            if metadata.get("mark_ids") != sorted([grainline_id, mark_id]):
                raise RuntimeError(export_format + " export lost persisted mark identity")

            output = first.decode("utf-8")
            if export_format == "SVG":
                if 'id="notch-%s"' % notch_id not in output:
                    raise RuntimeError("SVG export lost persisted notch identity/geometry")
                if 'id="mark-%s"' % grainline_id not in output:
                    raise RuntimeError("SVG export lost persisted grainline identity/geometry")
                if 'id="mark-%s"' % mark_id not in output or 'data-kind="InternalMark"' not in output:
                    raise RuntimeError("SVG export lost persisted construction-mark identity/geometry")
                if 'data-segment="%s" data-t="0.500000"' % edge_id not in output:
                    raise RuntimeError("SVG export lost persisted semantic mark reference")
                if 'cx="55.000000" cy="65.000000"' not in output:
                    raise RuntimeError("SVG export lost persisted notch coordinates")
                if 'x1="35.000000" y1="65.000000" x2="75.000000" y2="65.000000"' not in output:
                    raise RuntimeError("SVG export lost persisted construction-mark coordinates")
                if 'x1="37.000000" y1="65.000000" x2="73.000000" y2="65.000000"' not in output:
                    raise RuntimeError("SVG export lost persisted grainline coordinates")
            else:
                if '"notch_ids":["%s"]' % notch_id not in output:
                    raise RuntimeError("DXF export lost persisted notch identity")
                expected_mark_ids = json.dumps(sorted([grainline_id, mark_id]), separators=(",", ":"))
                if '"mark_ids":%s' % expected_mark_ids not in output:
                    raise RuntimeError("DXF export lost persisted mark identity")
                if "10\n50.000000\n20\n0.000000\n10\n50.000000\n20\n3.000000" not in output:
                    raise RuntimeError("DXF export lost persisted notch coordinates")
                if "10\n30.000000\n20\n0.000000\n10\n70.000000\n20\n0.000000" not in output:
                    raise RuntimeError("DXF export lost persisted construction-mark coordinates")
                if "10\n32.000000\n20\n0.000000\n10\n68.000000\n20\n0.000000" not in output:
                    raise RuntimeError("DXF export lost persisted grainline coordinates")

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
        )
        if source_before != after_export:
            raise RuntimeError("public export mutated authoritative PatternPiece/mark state")

        stale_path = output_dir / "stale.svg"
        notch.SegmentId = piece_id + ":edge:stale"
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

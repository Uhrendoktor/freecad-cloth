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


doc = None
try:
    record("smoke=started")
    InitGui.ClothPatternWorkbench()
    record("workbench=initialized")
    Gui.activateWorkbench("ClothPatternWorkbench")
    process_events()

    for command in ("ClothPattern_CreatePieceWithSketch", "ClothPattern_Export"):
        if command not in Gui.listCommands():
            raise RuntimeError("missing public Pattern command: " + command)
    record("commands=registered")

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

    source_before = (
        str(piece.Label),
        str(piece.PieceId),
        str(piece.SewingOutline),
        float(piece.SeamAllowance),
        float(piece.GrainlineAngle),
        str(getattr(piece, "GeometryAuthority", "")),
    )

    with tempfile.TemporaryDirectory() as directory:
        output_dir = Path(directory)
        panel = open_public_export(piece)
        record("export-panel=opened-initial")
        if "Production Export" not in panel.form.windowTitle():
            raise RuntimeError("export task panel title is not visible")
        if "read-only" not in panel.status.text().lower():
            raise RuntimeError("export task panel does not state that source geometry is read-only")
        close_public_task(panel)

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
            if not panel.accept():
                raise RuntimeError("public export task panel rejected " + export_format)
            process_events()
            record("export=%s:first-written" % export_format)

            first = path_a.read_bytes()
            if not first:
                raise RuntimeError(export_format + " export is empty")

            panel = open_public_export(piece)
            record("export=%s:second-panel-opened" % export_format)
            panel.format.setCurrentText(export_format)
            panel.path.setText(str(path_b))
            record("export=%s:second-accept" % export_format)
            if not panel.accept():
                raise RuntimeError("second public export rejected " + export_format)
            process_events()
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
sys.stdout.flush()
os._exit(0)

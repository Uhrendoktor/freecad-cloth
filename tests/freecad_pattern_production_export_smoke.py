"""Real FreeCAD/Xvfb acceptance fixture for the public production pattern export path."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import FreeCAD as App
import FreeCADGui as Gui
import InitGui

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

from freecad_cloth.pattern.PatternExport import from_dxf_metadata, from_svg_metadata, validate_export
from freecad_cloth.pattern.PatternMarks import add_mark
from freecad_cloth.pattern.PatternProductionExport import (
    PatternExportValidationError,
    build_export_source,
    export_pattern_piece,
)


def _process_events():
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def _source_snapshot(piece, sketch, marks, seam):
    return {
        "document_objects": tuple(obj.Name for obj in piece.Document.Objects),
        "piece": {
            "Label": str(piece.Label),
            "PieceId": str(piece.PieceId),
            "Width": float(piece.Width),
            "Height": float(piece.Height),
            "SeamAllowance": float(piece.SeamAllowance),
            "GrainlineAngle": float(piece.GrainlineAngle),
            "GeometryMode": str(piece.GeometryMode),
            "DraftingBoundary": str(piece.DraftingBoundary),
            "SewingOutline": str(piece.SewingOutline),
        },
        "sketch": {
            "Name": str(sketch.Name),
            "PatternPieceId": str(sketch.PatternPieceId),
            "GeometryAuthority": str(sketch.GeometryAuthority),
            "SemanticEdgeIds": tuple(str(value) for value in sketch.SemanticEdgeIds),
        },
        "marks": tuple(
            (
                str(obj.Name),
                str(obj.PatternMarkType),
                str(obj.PieceId),
                str(obj.SegmentId),
                float(obj.Position),
                float(obj.Depth),
                float(obj.Angle),
                float(obj.Length),
                str(obj.Text),
            )
            for obj in marks
        ),
        "seam": {
            "SeamId": str(seam.SeamId),
            "PieceA": str(seam.PieceA),
            "PieceB": str(seam.PieceB),
            "EdgeAId": str(seam.EdgeAId),
            "EdgeBId": str(seam.EdgeBId),
            "Status": str(seam.Status),
        },
    }


def main():
    output_dir = Path(os.environ.get("CLOTH_PATTERN_EXPORT_DIR", "/tmp/cloth-pattern-export"))
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.log"

    def progress(message):
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
            handle.flush()
        print("pattern-export-smoke:", message, flush=True)

    progress("start")
    workbench = InitGui.ClothPatternWorkbench()
    workbench.Initialize()
    Gui.activateWorkbench("Cloth Pattern")
    _process_events()
    assert "ClothPattern_ExportProduction" in Gui.listCommands()
    progress("workbench-ready")

    doc = App.newDocument("PatternProductionExportSmoke")
    progress("document-created")
    Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
    _process_events()
    piece = next(obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece")
    piece.Label = "Production Piece"
    piece.SeamAllowance = 6.0
    piece.GrainlineAngle = 90.0
    doc.recompute()

    marks = [
        add_mark(doc, "Notch", str(piece.PieceId), "bottom", 0.25, depth=4.0),
        add_mark(doc, "Grainline", str(piece.PieceId), "bottom", 0.5, angle=90.0, length=48.0, text="Grain"),
        add_mark(doc, "InternalMark", str(piece.PieceId), "top", 0.5, length=24.0, text="Drill"),
    ]
    progress("first-piece-created")
    other = create_pattern_piece()
    other.Label = "Mate Piece"
    doc.recompute()

    from freecad_cloth.pattern.PatternCommands import add_seam
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    Gui.Selection.addSelection(other)
    seam = add_seam()
    doc.recompute()
    assert str(seam.Status) == "Valid"
    progress("seam-valid")

    sketch = piece.Sketch
    before = _source_snapshot(piece, sketch, marks, seam)
    progress("source-snapshotted")

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    progress("before-public-command")
    Gui.runCommand("ClothPattern_ExportProduction", 0)
    _process_events()
    progress("after-public-command")
    panel = Gui.Control.activeDialog()
    assert panel is not None
    progress("panel-active")
    panel.output_prefix.setText(str(output_dir / "production-piece"))
    panel.units.setCurrentText("mm")
    panel.scale.setValue(1.0)
    assert panel.accept() is True
    _process_events()
    progress("first-export-complete")

    svg_path = output_dir / "production-piece.svg"
    dxf_path = output_dir / "production-piece.dxf"
    assert svg_path.is_file() and svg_path.stat().st_size > 0
    assert dxf_path.is_file() and dxf_path.stat().st_size > 0

    source = build_export_source(piece, units="mm", scale=1.0)
    progress("source-built")
    svg = svg_path.read_text(encoding="utf-8")
    dxf = dxf_path.read_text(encoding="utf-8")
    svg_metadata = from_svg_metadata(svg)
    dxf_metadata = from_dxf_metadata(dxf)

    assert svg_metadata["piece_id"] == str(piece.PieceId)
    assert dxf_metadata["piece_id"] == str(piece.PieceId)
    assert svg_metadata["units"] == "mm"
    assert dxf_metadata["units"] == "mm"
    assert svg_metadata["scale"] == 1.0
    assert dxf_metadata["scale"] == 1.0
    assert svg_metadata["seam_ids"] == [str(seam.SeamId)]
    assert dxf_metadata["seam_ids"] == [str(seam.SeamId)]
    assert "notch-Notch_1" in svg
    assert "mark-Grainline_1" in svg
    assert "mark-InternalMark_1" in svg
    assert svg_metadata["seam_allowance"] == 6.0
    assert dxf_metadata["seam_allowance"] == 6.0
    assert dxf_metadata["notch_ids"] == [str(marks[0].Name)]
    assert sorted(dxf_metadata["mark_ids"]) == sorted(str(mark.Name) for mark in marks[1:])
    assert '"scale":1.0' in dxf
    assert '"units":"mm"' in dxf

    validate_export(
        source.pattern,
        svg,
        "svg",
        curve_samples=64,
        units="mm",
        scale=1.0,
        derived=source.derived,
        piece_id=source.piece_id,
        seam_ids=source.seam_ids,
        seam_allowance=source.seam_allowance,
    )
    progress("metadata-parsed")
    validate_export(
        source.pattern,
        dxf,
        "dxf",
        curve_samples=64,
        units="mm",
        scale=1.0,
        derived=source.derived,
        piece_id=source.piece_id,
        seam_ids=source.seam_ids,
        seam_allowance=source.seam_allowance,
    )

    svg_again = export_pattern_piece(
        piece,
        output_dir / "production-piece-2.svg",
        output_dir / "production-piece-2.dxf",
        units="mm",
        scale=1.0,
    )
    assert svg_again.metadata["piece_id"] == str(piece.PieceId)
    assert (output_dir / "production-piece-2.svg").read_bytes() == svg_path.read_bytes()
    assert (output_dir / "production-piece-2.dxf").read_bytes() == dxf_path.read_bytes()
    progress("deterministic-round-trip")

    after = _source_snapshot(piece, sketch, marks, seam)
    assert after == before
    progress("source-unchanged")

    seam.EdgeAId = str(piece.PieceId) + ":edge:missing"
    doc.recompute()
    try:
        try:
            build_export_source(piece)
        except PatternExportValidationError as exc:
            assert "side A" in str(exc)
        else:
            raise AssertionError("invalid seam reference was not blocked")
    finally:
        seam.EdgeAId = before["seam"]["EdgeAId"]
        doc.recompute()
        progress("invalid-seam-check-complete")

    Gui.Control.closeDialog()
    _process_events()
    manifest = {
        "svg": str(svg_path.name),
        "dxf": str(dxf_path.name),
        "piece_id": str(piece.PieceId),
        "seam_ids": [str(seam.SeamId)],
        "edge_ids": svg_metadata["edge_ids"],
        "notch_ids": svg_metadata["notch_ids"],
        "mark_ids": svg_metadata["mark_ids"],
        "units": svg_metadata["units"],
        "scale": svg_metadata["scale"],
        "seam_allowance_mm": float(piece.SeamAllowance),
        "public_command": "ClothPattern_ExportProduction",
        "source_metadata": source.metadata,
        "source_unchanged": after == before,
        "deterministic_round_trip": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\\n",
        encoding="utf-8",
    )
    App.closeDocument(doc.Name)
    progress("done")
    print("Pattern production export smoke test passed: " + json.dumps(manifest, sort_keys=True))


main()

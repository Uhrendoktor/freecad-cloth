"""Focused native FreeCAD smoke test for the 3D Pattern Pen extraction boundary."""

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part

from freecad_cloth.pattern.SurfacePen import (
    SurfaceAnchor,
    create_surface_pen_object,
    extract_surface_draft_to_pattern,
)


def main():
    """Create a planar surface draft and verify native Sketcher extraction."""
    doc = App.newDocument("SurfacePenSmoke")
    try:
        target = doc.addObject("Part::Feature", "SurfacePenTarget")
        target.Shape = Part.makeBox(140.0, 100.0, 20.0)
        # Stabilize the authored target before persisting its provenance signature.
        # The extraction contract intentionally rejects drafts whose target changes
        # after authoring; recomputing first keeps this smoke fixture representative
        # of a completed target rather than an in-flight FreeCAD shape.
        doc.recompute()

        draft = create_surface_pen_object(
            doc,
            target,
            (
                SurfaceAnchor((10.0, 10.0, 20.0), (0.0, 0.0, 1.0)),
                SurfaceAnchor((110.0, 10.0, 20.0), (0.0, 0.0, 1.0)),
                SurfaceAnchor((110.0, 70.0, 20.0), (0.0, 0.0, 1.0)),
                SurfaceAnchor((10.0, 70.0, 20.0), (0.0, 0.0, 1.0)),
                SurfaceAnchor((10.0, 10.0, 20.0), (0.0, 0.0, 1.0)),
            ),
            label="3D Pen Smoke Draft",
        )
        doc.recompute()

        piece = extract_surface_draft_to_pattern(
            draft,
            tolerance_mm=0.5,
            name="3D Pen Smoke Piece",
        )
        doc.recompute()

        assert piece.PatternType == "PatternPiece"
        assert str(piece.GeometryAuthority) == "Sketcher"
        assert piece.Sketch is not None
        assert piece.Sketch.TypeId == "Sketcher::SketchObject"
        assert str(draft.Status) == "Extracted"
        assert len(tuple(piece.Sketch.Geometry)) == 4

        Path("artifacts").mkdir(parents=True, exist_ok=True)
        Path("artifacts/surface-pen.log").write_text(
            "surface-pen-native-smoke=passed\n",
            encoding="utf-8",
        )
        print("surface-pen-native-smoke=passed", flush=True)
    finally:
        App.closeDocument(doc.Name)


try:
    main()
    os._exit(0)
except BaseException as exc:
    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/surface-pen.log").write_text(
        "surface-pen-native-smoke=failed\n"
        + repr(exc)
        + "\n"
        + traceback.format_exc(),
        encoding="utf-8",
    )
    print("surface-pen-native-smoke=failed", repr(exc), flush=True)
    print(traceback.format_exc(), flush=True)
    os._exit(1)

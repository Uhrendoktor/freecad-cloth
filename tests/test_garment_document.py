"""Headless FreeCAD checks for the native Garment document contract."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import FreeCAD as App
except ImportError:
    App = None

from freecad_cloth.common.GarmentDocument import (
    GARMENT_GROUPS,
    create_garment_document,
    garment_root,
    garment_structure,
)
from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternObjects import add_pattern_piece
from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece


def run():
    if App is None:
        print("native Garment document contract skipped: FreeCAD module unavailable")
        return
    doc = create_garment_document("GarmentDocumentContract")
    restored = None
    try:
        root = garment_root(doc)
        assert root is not None
        assert root.TypeId == "App::Part"
        assert [obj.Name for obj in root.Group] == list(GARMENT_GROUPS)
        assert len(doc.getObject("Fabric").Group) == 1

        piece = PatternPiece("Front", [(0, 0), (20, 0), (20, 10), (0, 10)], id="front")
        obj = add_pattern_piece(doc, piece)
        sketch = create_sketch_for_piece(piece, doc)
        doc.recompute()
        assert obj in doc.getObject("Patterns").Group
        assert sketch in doc.getObject("Patterns").Group
        assert obj.Sketch is sketch
        assert obj.Garment.Name == root.Name

        fd, path = tempfile.mkstemp(suffix=".FCStd")
        os.close(fd)
        try:
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            doc = None
            restored = App.openDocument(path)
            restored.recompute()
            root = garment_root(restored)
            assert root is not None
            structure = garment_structure(restored)
            assert [item["name"] for item in structure["groups"]["Patterns"]] == sorted(
                [restored.getObject("Front").Name, restored.getObject(sketch.Name).Name]
            )
            restored_piece = restored.getObject("Front")
            assert restored_piece.Sketch is not None
            assert restored_piece.Sketch.Name == sketch.Name
            print("native Garment document contract passed")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    finally:
        if restored is not None and restored.Name in App.listDocuments():
            App.closeDocument(restored.Name)
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    run()

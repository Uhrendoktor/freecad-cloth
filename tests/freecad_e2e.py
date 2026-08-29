"""Canonical real-FreeCAD garment workflow acceptance fixture.

This intentionally drives the registered workbench commands and native
Sketcher objects rather than constructing a private PatternModel-only scene.
"""
import math
import os
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher


def _pieces(doc):
    return [o for o in doc.Objects if getattr(o, "PatternType", "") == "PatternPiece"]


def _select(obj, *subelements):
    Gui.Selection.clearSelection()
    if subelements:
        for name in subelements:
            Gui.Selection.addSelection(obj, name)
    else:
        Gui.Selection.addSelection(obj)


def _run(command):
    Gui.runCommand(command)
    App.ActiveDocument.recompute()


def _create_piece(command):
    before = {getattr(o, "Name", "") for o in _pieces(App.ActiveDocument)}
    _run(command)
    created = [o for o in _pieces(App.ActiveDocument) if o.Name not in before]
    if not created:
        raise AssertionError(f"{command} did not create a PatternPiece")
    return created[-1]


def _create_sketch(piece):
    _select(piece)
    _run("ClothPattern_CreateSketch")
    sketch = getattr(piece, "Sketch", None)
    if sketch is None or getattr(sketch, "GeometryAuthority", "") != "Sketcher":
        raise AssertionError("CreateSketch did not establish Sketcher authority")
    return sketch


def _make_curved(sketch):
    """Replace the demo rectangle with a closed native arc/line boundary."""
    sketch.clear()
    geometry = [
        Part.ArcOfCircle(Part.Circle(App.Vector(50, 0, 0), App.Vector(0, 0, 1), 50), math.pi, math.tau),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 60, 0)),
        Part.LineSegment(App.Vector(100, 60, 0), App.Vector(0, 60, 0)),
        Part.LineSegment(App.Vector(0, 60, 0), App.Vector(0, 0, 0)),
    ]
    sketch.addGeometry(geometry, False)
    sketch.addConstraint(Sketcher.Constraint("Distance", 1, 60.0))
    sketch.SemanticEdgeIds = [
        f"{sketch.PatternPieceId}:edge:0",
        f"{sketch.PatternPieceId}:edge:1",
        f"{sketch.PatternPieceId}:edge:2",
        f"{sketch.PatternPieceId}:edge:3",
    ]
    sketch.GeometryAuthority = "Sketcher"
    sketch.Document.recompute()


def main():
    doc = App.newDocument("ClothCanonicalGarment")
    Gui.activeDocument().activeView().viewTop()

    Gui.activateWorkbench("Cloth Pattern")
    front = _create_piece("ClothPattern_CreatePiece")
    middle = _create_piece("ClothPattern_CreateCustomPiece")
    back = _create_piece("ClothPattern_CreatePiece")
    front_sketch = _create_sketch(front)
    middle_sketch = _create_sketch(middle)
    back_sketch = _create_sketch(back)
    _make_curved(front_sketch)
    doc.recompute()

    if len(_pieces(doc)) != 3:
        raise AssertionError("canonical fixture must contain three PatternPieces")
    if front.Height <= 60.0 or len(front.Shape.Edges) < 4:
        raise AssertionError("curved Sketcher edit did not propagate to PatternPiece")

    Gui.activateWorkbench("Cloth Sewing")
    _select(front, "Edge1")
    Gui.Selection.addSelection(middle, "Edge1")
    _run("ClothPattern_AddSeam")
    _select(middle, "Edge1")
    Gui.Selection.addSelection(back, "Edge1")
    _run("ClothPattern_AddSeam")
    seams = [o for o in doc.Objects if getattr(o, "SeamId", "")]
    if len(seams) < 2:
        raise AssertionError("canonical fixture must contain two persisted seams")

    Gui.activateWorkbench("Cloth Simulation")
    _run("ClothSimulation_Create")
    scene = next((o for o in doc.Objects if getattr(o, "Type", "") == "ClothSimulation"), None)
    if scene is None:
        raise AssertionError("simulation scene was not created")
    scene.ClothPieces = _pieces(doc)
    scene.QualityPreset = "Fast"
    scene.Steps = 4
    doc.recompute()
    if scene.ParticleCount <= 0 or not scene.FiniteState:
        raise AssertionError("simulation did not produce a finite particle state")
    working_particles = int(scene.ParticleCount)
    scene.QualityPreset = "Final"
    scene.Steps = 1
    doc.recompute()
    final_particles = int(scene.ParticleCount)
    if final_particles <= working_particles:
        raise AssertionError("final quality did not increase deterministic mesh density")

    artifact_dir = Path(os.environ.get("CLOTH_E2E_DIR", "artifacts/freecad-e2e"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "canonical-garment.FCStd"
    doc.recompute()
    doc.saveAs(str(path))
    Gui.Selection.clearSelection()
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(path))
    reopened.recompute()
    reopened_pieces = _pieces(reopened)
    reopened_seams = [o for o in reopened.Objects if getattr(o, "SeamId", "")]
    if len(reopened_pieces) != 3 or len(reopened_seams) < 2:
        raise AssertionError("save/reload lost pattern or seam objects")
    if any(getattr(piece, "GeometryAuthority", "") != "Sketcher" for piece in reopened_pieces):
        raise AssertionError("save/reload lost Sketcher geometry authority")

    edited = reopened_pieces[0]
    edited_sketch = edited.Sketch
    before_height = float(edited.Height)
    edited_sketch.setDatum(0, App.Units.Quantity("80 mm"))
    reopened.recompute()
    after_height = float(edited.Height)
    if abs(after_height - before_height) < 1e-6:
        raise AssertionError("native Sketcher dimensional edit did not invalidate/rebuild PatternPiece")

    reopened_scene = next((o for o in reopened.Objects if getattr(o, "Type", "") == "ClothSimulation"), None)
    if reopened_scene is None:
        raise AssertionError("save/reload lost simulation scene")
    reopened_scene.ClothPieces = reopened_pieces
    reopened_scene.Steps = 1
    reopened.recompute()
    if reopened_scene.ParticleCount <= 0 or not reopened_scene.FiniteState:
        raise AssertionError("re-simulation after upstream edit did not succeed")

    with open(artifact_dir / "workflow.log", "w", encoding="utf-8") as handle:
        handle.write("three PatternPieces: OK\n")
        handle.write("native curved Sketcher boundary: OK\n")
        handle.write("two persisted seams: OK\n")
        handle.write(f"quality density {working_particles} -> {final_particles}: OK\n")
        handle.write("save/reload: OK\n")
        handle.write(f"Sketcher edit height {before_height} -> {after_height}: OK\n")
        handle.write("re-simulation after edit: OK\n")
    print("canonical garment workflow passed")


if __name__ == "__main__":
    main()

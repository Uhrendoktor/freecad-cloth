"""Real-FreeCAD smoke for the native Garment document hierarchy.

Create production Garment -> populate native objects -> save/reload -> verify
exact group structure and persistent links.  The FCStd file is the persistence
authority; the JSON manifest is evidence only.
"""
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

ROOT = Path.cwd()
if not (ROOT / "InitGui.py").exists():
    ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
init_gui = ROOT / "InitGui.py"
exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), globals(), globals())

OUT = Path(os.environ.get("CLOTH_GARMENT_HIERARCHY_OUT", "artifacts/garment-hierarchy-smoke"))
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "garment-hierarchy-smoke.log"
FCSTD = OUT / "garment-hierarchy-smoke.FCStd"
MANIFEST = OUT / "garment-hierarchy-smoke.json"


def log(message):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()


def group_names(container):
    return [str(obj.Name) for obj in getattr(container, "Group", ())]


def find_role(group, role):
    return [obj for obj in getattr(group, "Group", ()) if str(getattr(obj, "GarmentRole", "")) == role]


def verify(doc, label):
    from freecad_cloth.common.GarmentDocument import GARMENT_GROUPS, garment_group, garment_root, garment_structure

    root = garment_root(doc)
    assert root is not None, "missing Garment root"
    assert str(root.TypeId) == "App::Part", root.TypeId
    assert group_names(root) == list(GARMENT_GROUPS), group_names(root)

    groups = {role: garment_group(doc, role) for role in GARMENT_GROUPS}
    assert all(groups.values()), "one or more Garment containers are missing"
    assert all(str(getattr(groups[role], "GarmentRole", "")) == role for role in GARMENT_GROUPS)

    patterns = groups["Patterns"]
    sewing = groups["Sewing"]
    fabric = groups["Fabric"]
    avatar_group = groups["Avatar"]
    simulation = groups["Simulation"]

    pieces = [obj for obj in patterns.Group if getattr(obj, "PatternType", "") == "PatternPiece"]
    sketches = [obj for obj in patterns.Group if str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject"]
    seams = [obj for obj in sewing.Group if getattr(obj, "SeamId", "")]
    operations = [obj for obj in sewing.Group if getattr(obj, "SewingType", "") == "SewingOperation"]
    material = next((obj for obj in fabric.Group if str(getattr(obj, "GarmentRole", "")) == "FabricMaterial"), None)
    avatar = next((obj for obj in avatar_group.Group if str(getattr(obj, "AvatarType", "")) == "ClothAvatar"), None)
    target = next((obj for obj in avatar_group.Group if str(getattr(obj, "Name", "")) == "DrapeTarget"), None)
    scene = next((obj for obj in simulation.Group if str(getattr(obj, "Name", "")) == "ClothSimulation"), None)

    assert len(pieces) == 2, [p.Name for p in pieces]
    assert len(sketches) == 2, [s.Name for s in sketches]
    assert len(seams) == 1, [s.Name for s in seams]
    assert len(operations) == 1, [o.Name for o in operations]
    assert material is not None
    assert avatar is not None
    assert target is not None
    assert scene is not None

    front = next(obj for obj in pieces if str(obj.PieceId) == "front")
    back = next(obj for obj in pieces if str(obj.PieceId) == "back")
    assert front.Sketch is not None and str(front.Sketch.PatternPieceId) == "front"
    assert back.Sketch is not None and str(back.Sketch.PatternPieceId) == "back"

    seam = seams[0]
    operation = operations[0]
    assert seam.PatternA is front and seam.PatternB is back
    assert operation.Seam is seam and operation.PieceA is front and operation.PieceB is back
    assert scene.FabricMaterial is material
    assert scene.DrapeTarget is target
    assert target.SourceObject is avatar
    assert {obj.Name for obj in scene.ClothPieces} >= {front.Name, back.Name}

    structure = garment_structure(doc)
    manifest = {
        "label": label,
        "document": str(doc.Name),
        "fcstd": FCSTD.name,
        "hierarchy": structure,
        "links": {
            "front_sketch": front.Sketch.Name,
            "back_sketch": back.Sketch.Name,
            "seam_pattern_a": seam.PatternA.Name,
            "seam_pattern_b": seam.PatternB.Name,
            "operation_seam": operation.Seam.Name,
            "operation_piece_a": operation.PieceA.Name,
            "operation_piece_b": operation.PieceB.Name,
            "fabric_material": material.Name,
            "avatar": avatar.Name,
            "drape_target": target.Name,
            "target_source": target.SourceObject.Name,
            "simulation": scene.Name,
            "simulation_fabric": scene.FabricMaterial.Name,
            "simulation_target": scene.DrapeTarget.Name,
            "simulation_pieces": [obj.Name for obj in scene.ClothPieces],
        },
    }
    return manifest


def make_piece(doc, name, piece_id, x):
    from freecad_cloth.pattern.PatternModel import PatternPiece
    from freecad_cloth.pattern.PatternObjects import add_pattern_piece
    from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece

    piece = PatternPiece(
        name,
        [(0, 0), (100, 0), (100, 60), (0, 60)],
        seam_allowance=5.0,
        grainline_angle=0.0,
        id=piece_id,
    )
    obj = add_pattern_piece(doc, piece)
    obj.Placement.Base.x = float(x)
    sketch = create_sketch_for_piece(piece, doc)
    doc.recompute()
    assert obj.Sketch is sketch
    return obj


def run():
    doc = None
    path = FCSTD
    try:
        log("scenario-start")
        Gui.activateWorkbench("ClothPatternWorkbench")
        Gui.runCommand("ClothPattern_CreateGarment", 0)
        doc = App.ActiveDocument
        assert doc is not None
        from freecad_cloth.common.GarmentDocument import garment_root
        assert garment_root(doc) is not None
        log("production-garment-command=passed")

        from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
        scene = create_simulation_scene(doc)
        assert scene.FabricMaterial is not None
        assert scene.DrapeTarget is not None
        log("populate-fabric-avatar-simulation=passed")

        front = make_piece(doc, "Front", "front", 0)
        back = make_piece(doc, "Back", "back", 130)

        from freecad_cloth.pattern.PatternModel import Seam
        from freecad_cloth.pattern.PatternObjects import add_seam
        from freecad_cloth.sewing.SewingObjects import add_sewing_operation
        seam = add_seam(doc, Seam("front", 1, "back", 3, id="side-seam"))
        operation = add_sewing_operation(doc, seam, front, back, "SideSewing")
        doc.recompute()
        assert str(seam.Status) == "Valid"
        assert str(operation.Status) == "Valid"
        scene.ClothPieces = [front, back]
        log("populate-pattern-sewing=passed")

        before = verify(doc, "before-save")
        doc.recompute()
        doc.saveAs(str(path))
        log("save=passed path=%s" % path)

        saved_name = doc.Name
        App.closeDocument(saved_name)
        doc = App.openDocument(str(path))
        after = verify(doc, "after-reload")
        assert before["hierarchy"] == after["hierarchy"], "hierarchy changed after reload"
        assert before["links"] == after["links"], "object links changed after reload"
        log("reload=passed")
        log("hierarchy-verification=passed")
        log("standalone-backcompat-start")
        legacy = App.newDocument("LegacyStandalone")
        try:
            from freecad_cloth.pattern.PatternModel import PatternPiece
            from freecad_cloth.pattern.PatternObjects import add_pattern_piece
            legacy_piece = add_pattern_piece(
                legacy,
                PatternPiece("Legacy", [(0, 0), (20, 0), (20, 10)], id="legacy"),
            )
            assert not any(str(getattr(obj, "GarmentRole", "")) == "GarmentRoot" for obj in legacy.Objects)
            assert legacy_piece in legacy.Objects
        finally:
            App.closeDocument(legacy.Name)
        log("standalone-backcompat=passed")

        MANIFEST.write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
        log("artifact-manifest=passed path=%s" % MANIFEST)
        log("scenario-complete")
    except Exception:
        log("scenario-error")
        log(traceback.format_exc())
        raise
    finally:
        try:
            if doc is not None and doc.Name in App.listDocuments():
                App.closeDocument(doc.Name)
        except Exception:
            pass
        try:
            window = Gui.getMainWindow()
            if window is not None:
                window.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()

"""Real-FreeCAD persistence smoke for the native Garment hierarchy."""
import json
import os
import sys
import traceback
from pathlib import Path

import FreeCAD as App

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SMOKE_SCHEMA_VERSION = "1"
OUT = Path(os.environ.get("CLOTH_GARMENT_HIERARCHY_OUT", "artifacts/garment-hierarchy-smoke"))
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "garment-hierarchy-smoke.log"
FCSTD = OUT / "garment-hierarchy-smoke.FCStd"
MANIFEST = OUT / "garment-hierarchy-smoke.json"


def log(message):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()


def children(obj):
    return tuple(getattr(obj, "Group", ()) or ())


def require_group(doc, name):
    group = doc.getObject(name)
    assert group is not None, "missing group " + name
    return group


def make_piece(doc, name, piece_id, x):
    from freecad_cloth.pattern.PatternModel import PatternPiece
    from freecad_cloth.pattern.PatternObjects import add_pattern_piece
    from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece

    piece = PatternPiece(
        name,
        [(0, 0), (100, 0), (100, 60), (0, 60)],
        id=piece_id,
    )
    obj = add_pattern_piece(doc, piece)
    obj.Placement.Base.x = float(x)
    sketch = create_sketch_for_piece(piece, doc)
    doc.recompute()
    assert obj.Sketch is sketch
    return obj


def snapshot(doc):
    from freecad_cloth.common.GarmentDocument import GARMENT_GROUPS, garment_root, garment_structure

    root = garment_root(doc)
    assert root is not None
    assert root.TypeId == "App::Part"
    assert [obj.Name for obj in children(root)] == list(GARMENT_GROUPS)

    patterns = require_group(doc, "Patterns")
    sewing = require_group(doc, "Sewing")
    fabric = require_group(doc, "Fabric")
    avatar = require_group(doc, "Avatar")
    simulation = require_group(doc, "Simulation")

    pieces = [obj for obj in children(patterns) if getattr(obj, "PatternType", "") == "PatternPiece"]
    sketches = [obj for obj in children(patterns) if getattr(obj, "TypeId", "") == "Sketcher::SketchObject"]
    seams = [obj for obj in children(sewing) if getattr(obj, "SeamId", "")]
    operations = [obj for obj in children(sewing) if getattr(obj, "SewingType", "") == "SewingOperation"]
    material = next((obj for obj in children(fabric) if getattr(obj, "GarmentRole", "") == "FabricMaterial"), None)
    humanoid = next((obj for obj in children(avatar) if getattr(obj, "AvatarType", "") == "ClothAvatar"), None)
    collision = next((obj for obj in children(avatar) if getattr(obj, "Name", "") == "AvatarCollision"), None)
    target = next((obj for obj in children(avatar) if getattr(obj, "Name", "") == "DrapeTarget"), None)
    scene = next((obj for obj in children(simulation) if getattr(obj, "Name", "") == "ClothSimulation"), None)

    assert len(pieces) == 2, [obj.Name for obj in pieces]
    assert len(sketches) == 2, [obj.Name for obj in sketches]
    assert len(seams) == 1, [obj.Name for obj in seams]
    assert len(operations) == 1, [obj.Name for obj in operations]
    assert material is not None
    assert humanoid is not None
    assert collision is not None
    assert target is not None
    assert scene is not None

    front = next(obj for obj in pieces if obj.PieceId == "front")
    back = next(obj for obj in pieces if obj.PieceId == "back")
    seam = seams[0]
    operation = operations[0]

    assert front.Sketch is not None and front.Sketch.Name in {obj.Name for obj in sketches}
    assert back.Sketch is not None and back.Sketch.Name in {obj.Name for obj in sketches}
    assert seam.PatternA is front and seam.PatternB is back
    assert operation.Seam is seam
    assert operation.PieceA is front and operation.PieceB is back
    assert scene.FabricMaterial is material
    assert scene.DrapeTarget is target
    assert target.SourceObject is humanoid
    assert collision.SourceObject is humanoid
    assert {obj.Name for obj in scene.ClothPieces} == {front.Name, back.Name}

    return {
        "hierarchy": garment_structure(doc),
        "links": {
            "front_sketch": front.Sketch.Name,
            "back_sketch": back.Sketch.Name,
            "seam_piece_a": seam.PatternA.Name,
            "seam_piece_b": seam.PatternB.Name,
            "operation_seam": operation.Seam.Name,
            "operation_piece_a": operation.PieceA.Name,
            "operation_piece_b": operation.PieceB.Name,
            "fabric_material": material.Name,
            "simulation_fabric": scene.FabricMaterial.Name,
            "avatar": humanoid.Name,
            "collision_source": collision.SourceObject.Name,
            "drape_target": target.Name,
            "target_source": target.SourceObject.Name,
            "simulation": scene.Name,
            "simulation_pieces": sorted(obj.Name for obj in scene.ClothPieces),
        },
    }


def run():
    doc = None
    restored = None
    try:
        log("scenario-start")
        from freecad_cloth.pattern.PatternCommands import create_garment
        doc = create_garment(name="GarmentHierarchySmoke")
        assert doc is not None
        log("production-garment-path=passed")

        front = make_piece(doc, "Front", "front", 0)
        back = make_piece(doc, "Back", "back", 130)

        from freecad_cloth.pattern.PatternModel import Seam
        from freecad_cloth.pattern.PatternObjects import add_seam
        from freecad_cloth.sewing.SewingObjects import add_sewing_operation
        seam = add_seam(doc, Seam("front", 1, "back", 1, id="side-seam"))
        operation = add_sewing_operation(doc, seam, front, back, "SideSewing")
        doc.recompute()
        assert str(seam.Status) == "Valid"
        assert str(operation.Status) == "Valid"
        log("populate-pattern-sewing=passed")

        import Part
        from freecad_cloth.common.GarmentDocument import link_garment_object
        avatar = doc.addObject("Part::Feature", "ClothAvatarSmoke")
        avatar.Label = "Cloth Avatar"
        avatar.Shape = Part.makeCylinder(40.0, 160.0)
        avatar.addProperty("App::PropertyString", "AvatarType", "Avatar").AvatarType = "ClothAvatar"
        link_garment_object(avatar, "Avatar", doc)

        from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
        scene = create_simulation_scene(doc, build=False, avatar_source=avatar)
        scene.ClothPieces = [front, back]
        assert scene.FabricMaterial is not None
        assert scene.DrapeTarget is not None
        assert scene.FabricMaterial in children(require_group(doc, "Fabric"))
        assert scene.DrapeTarget in children(require_group(doc, "Avatar"))
        log("populate-fabric-avatar-simulation=passed")

        before = snapshot(doc)
        doc.saveAs(str(FCSTD))
        log("save=passed")
        App.closeDocument(doc.Name)
        doc = None

        restored = App.openDocument(str(FCSTD))
        after = snapshot(restored)
        assert before["hierarchy"] == after["hierarchy"], "hierarchy changed after reload"
        assert before["links"] == after["links"], "links changed after reload"
        log("reload=passed")
        log("hierarchy-verification=passed")

        legacy = App.newDocument("LegacyStandalone")
        try:
            from freecad_cloth.pattern.PatternModel import PatternPiece
            from freecad_cloth.pattern.PatternObjects import add_pattern_piece
            legacy_piece = add_pattern_piece(
                legacy,
                PatternPiece("Legacy", [(0, 0), (20, 0), (20, 10)], id="legacy"),
            )
            assert legacy_piece in legacy.Objects
            assert not any(getattr(obj, "GarmentRole", "") == "GarmentRoot" for obj in legacy.Objects)
        finally:
            App.closeDocument(legacy.Name)
        log("standalone-backcompat=passed")

        MANIFEST.write_text(
            json.dumps(
                {
                    "smoke_schema_version": SMOKE_SCHEMA_VERSION,
                    "fcstd": FCSTD.name,
                    "hierarchy": after["hierarchy"],
                    "links": after["links"],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        log("artifact-manifest=passed")
        log("scenario-complete")
    except Exception:
        log("scenario-error")
        log(traceback.format_exc())
        raise
    finally:
        for candidate in (restored, doc):
            try:
                if candidate is not None and candidate.Name in App.listDocuments():
                    App.closeDocument(candidate.Name)
            except Exception:
                pass


if __name__ == "__main__":
    run()

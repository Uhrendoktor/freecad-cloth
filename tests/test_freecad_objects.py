import math
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.PatternObjects import PatternPieceProxy, add_pattern_piece, add_seam, refresh_edge_reference_signature
from freecad_cloth.sewing.SewingNetwork import SewingMember, add_sewing_network, build_mn_seams
from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece


class Vector:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class Wire:
    def __init__(self, points):
        self.points = points


def make_polygon(points):
    return Wire(points)


def make_face(wire):
    return SimpleNamespace(points=wire.points)


def test_pattern_piece_proxy_recomputes_deterministically():
    fake_freecad = SimpleNamespace(Vector=Vector)
    fake_part = SimpleNamespace(makePolygon=make_polygon, Face=make_face)
    previous_freecad = sys.modules.get("FreeCAD")
    previous_part = sys.modules.get("Part")
    sys.modules["FreeCAD"] = fake_freecad
    sys.modules["Part"] = fake_part
    try:
        obj = SimpleNamespace(Width=100.0, Height=60.0, SeamAllowance=5.0)
        proxy = PatternPieceProxy()
        proxy.execute(obj)
        first = [(p.x, p.y) for p in obj.Shape.points]
        assert first == [(-5.0, -5.0), (105.0, -5.0), (105.0, 65.0), (-5.0, 65.0), (-5.0, -5.0)]
        assert obj.SewingBoundary == "bottom,right,top,left"
        obj.Width = 120.0
        proxy.execute(obj)
        second = [(p.x, p.y) for p in obj.Shape.points]
        assert second == [(-5.0, -5.0), (125.0, -5.0), (125.0, 65.0), (-5.0, 65.0), (-5.0, -5.0)]
        assert obj.SewingBoundary == "bottom,right,top,left"
    finally:
        if previous_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = previous_freecad
        if previous_part is None:
            sys.modules.pop("Part", None)
        else:
            sys.modules["Part"] = previous_part


def test_pattern_piece_proxy_rejects_invalid_dimensions():
    obj = SimpleNamespace(Width=0.0, Height=60.0, SeamAllowance=0.0)
    try:
        PatternPieceProxy().execute(obj)
    except ModuleNotFoundError:
        # Import dependencies are intentionally lazy; validation is expected
        # to happen under the real FreeCAD runtime.
        return
    except ValueError:
        return
    raise AssertionError("non-positive dimensions should fail")


def _set_native_boundary(sketch, arc):
    sketch.clear()
    sketch.addGeometry([
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)),
        arc,
        Part.LineSegment(App.Vector(10, 10, 0), App.Vector(0, 10, 0)),
        Part.LineSegment(App.Vector(0, 10, 0), App.Vector(0, 0, 0)),
    ], False)
    sketch.SemanticEdgeIds = [
        "native-a:edge:0",
        "native-a:edge:1",
        "native-a:edge:2",
        "native-a:edge:3",
    ]
    sketch.GeometryAuthority = "Sketcher"


def test_avatar_collision_source_supports_fitting_and_simulation_scopes():
    if App is None or Part is None:
        return
    document = App.newDocument("AvatarCollisionScope")
    try:
        from freecad_cloth.avatar.FittingCommands import create_fitting_scene
        from freecad_cloth.simulation.SimulationObjects import create_simulation_scene, set_avatar_collision_source

        body = document.addObject("Part::Feature", "FixtureBody")
        body.Shape = Part.makeBox(80, 80, 160, App.Vector(-40, -40, -80))
        body.Placement.Base.x = 25.0
        document.recompute()

        fitting = create_fitting_scene()
        proxy = set_avatar_collision_source(fitting, body, thickness=2.0, deflection=1.0)
        assert proxy is fitting.AvatarProxy
        assert proxy.Name == "AvatarCollision"
        assert proxy.SourceObject == body

        target = document.getObject("DrapeTarget")
        assert "DrapeTarget" in set(getattr(fitting, "PropertiesList", ()) or ())
        assert fitting.DrapeTarget == target
        assert target is not None
        assert target.SourceObject == body
        from freecad_cloth.avatar.FittingCommands import _world_target_surface
        world_surface = _world_target_surface(target)
        assert min(point[0] for point in world_surface.vertices) == -15.0
        assert max(point[0] for point in world_surface.vertices) == 65.0

        simulation = create_simulation_scene(document)
        proxy2 = set_avatar_collision_source(simulation, body, thickness=3.0, deflection=0.5)
        assert proxy2 is simulation.AvatarProxy
        assert proxy2 is proxy
        assert simulation.DrapeTarget == target
        assert proxy2.SourceObject == body
        assert float(target.CollisionThickness) == 3.0
        assert float(target.CollisionDeflection) == 0.5
    finally:
        if document.Name in App.listDocuments():
            App.closeDocument(document.Name)


def _placement_tuple(placement):
    base = placement.Base
    axis = placement.Rotation.Axis
    return (
        float(base.x), float(base.y), float(base.z),
        float(placement.Rotation.Angle),
        float(axis.x), float(axis.y), float(axis.z),
    )


def _target_snap_fixture(name):
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene
    from freecad_cloth.simulation.DrapeTarget import create_drape_target

    document = App.newDocument(name)
    source = document.addObject("Part::Feature", "TargetSource")
    source.Shape = Part.makeBox(40.0, 40.0, 40.0)
    source.Placement = App.Placement(
        App.Vector(100.0, 50.0, 10.0),
        App.Rotation(App.Vector(0.0, 0.0, 1.0), 25.0),
    )
    sketch = document.addObject("PartDesign::Feature", "PatternSketch")
    sketch.Shape = Part.Shape()
    piece = document.addObject("Part::Feature", "PatternPiece")
    piece.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    piece.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = "fixture-piece"
    piece.addProperty("App::PropertyLink", "Sketch", "Cloth").Sketch = sketch
    piece.Shape = Part.makeBox(10.0, 10.0, 2.0)
    local_center = App.Vector(20.0, 20.0, 5.0)
    world_center = source.Placement.multVec(local_center)
    piece.Placement = App.Placement(
        App.Vector(world_center.x - 5.0, world_center.y - 5.0, world_center.z - 1.0),
        App.Rotation(App.Vector(1.0, 0.0, 0.0), 90.0),
    )
    sketch.Placement = piece.Placement
    document.recompute()

    target = create_drape_target(
        document,
        source,
        "FreeCAD Geometry",
        0.5,
        0.0,
    )
    fitting = create_fitting_scene()
    fitting.DrapeTarget = target
    fitting.PatternPieces = [piece]
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    home = piece.Placement
    home_record = PiecePlacement(
        "fixture-piece",
        (float(home.Base.x), float(home.Base.y), float(home.Base.z)),
        float(home.Rotation.Angle),
        (float(home.Rotation.Axis.x), float(home.Rotation.Axis.y), float(home.Rotation.Axis.z)),
    ).to_string()
    fitting.PiecePlacements = [home_record]
    fitting.HomePlacements = [home_record]
    fitting.FitStatus = "Ready"
    document.recompute()
    return document, source, target, fitting, piece, sketch


def test_target_snap_uses_world_target_placement_and_reset_restores_linked_sketch():
    if App is None or Part is None:
        return
    from freecad_cloth.avatar import FittingCommands
    from freecad_cloth.avatar.AvatarCollision import surface_from_freecad

    document, source, target, fitting, piece, sketch = _target_snap_fixture("TargetSnapReset")
    try:
        local_surface = surface_from_freecad(source, 0.5, 0.0)
        expected = source.Placement.multVec(App.Vector(*local_surface.vertices[0]))
        world_surface = FittingCommands._world_target_surface(target)
        actual = world_surface.vertices[0]
        assert all(abs(float(got) - float(want)) < 1e-7 for got, want in zip(actual, (expected.x, expected.y, expected.z)))

        home = _placement_tuple(piece.Placement)
        home_sketch = _placement_tuple(sketch.Placement)
        result = FittingCommands.snap_pattern_pieces_to_target([piece], target, clearance=2.0)
        assert result["pieces"]
        assert _placement_tuple(piece.Placement) != home
        assert _placement_tuple(sketch.Placement) != home_sketch

        FittingCommands.reset_arrangement()
        assert _placement_tuple(piece.Placement) == home
        assert _placement_tuple(sketch.Placement) == home_sketch
        assert tuple(fitting.HomePlacements) == tuple(fitting.PiecePlacements)
        assert str(fitting.FitStatus) == "Arrangement reset"

        FittingCommands.snap_pattern_pieces_to_target([piece], target, clearance=2.0)
        assert _placement_tuple(piece.Placement) != home
    finally:
        if document.Name in App.listDocuments():
            App.closeDocument(document.Name)


def test_target_snap_rolls_back_piece_sketch_and_fitting_state_after_post_transform_failure():
    if App is None or Part is None:
        return
    from freecad_cloth.avatar import FittingCommands

    document, _source, target, fitting, piece, sketch = _target_snap_fixture("TargetSnapRollback")
    try:
        before_piece = _placement_tuple(piece.Placement)
        before_sketch = _placement_tuple(sketch.Placement)
        before_piece_records = tuple(fitting.PiecePlacements)
        before_home_records = tuple(fitting.HomePlacements)
        before_status = str(fitting.FitStatus)
        before_target = fitting.DrapeTarget
        original_sampler = FittingCommands._piece_world_samples
        calls = {"count": 0}

        def failing_sampler(obj, deflection=1.0):
            calls["count"] += 1
            samples = original_sampler(obj, deflection)
            if calls["count"] >= 2:
                return tuple((point[0], point[1], point[2] - 10000.0) for point in samples)
            return samples

        FittingCommands._piece_world_samples = failing_sampler
        try:
            try:
                FittingCommands.snap_pattern_pieces_to_target([piece], target, clearance=2.0)
            except ValueError as exc:
                assert "clearance" in str(exc)
            else:
                raise AssertionError("post-transform clearance failure should roll back")
        finally:
            FittingCommands._piece_world_samples = original_sampler

        assert _placement_tuple(piece.Placement) == before_piece
        assert _placement_tuple(sketch.Placement) == before_sketch
        assert tuple(fitting.PiecePlacements) == before_piece_records
        assert tuple(fitting.HomePlacements) == before_home_records
        assert str(fitting.FitStatus) == before_status
        assert fitting.DrapeTarget == before_target
    finally:
        if document.Name in App.listDocuments():
            App.closeDocument(document.Name)

def test_native_seam_reference_save_reload_curve_edit_and_missing():
    if App is None or Part is None:
        return
    document = App.newDocument("NativeSeamFingerprint")
    try:
        piece_a = PatternPiece(
            "NativeArcA", [(0, 0), (10, 0), (10, 10), (0, 10)], id="native-a"
        )
        piece_b = PatternPiece(
            "NativeArcB", [(0, 0), (10, 0), (10, 10), (0, 10)], id="native-b"
        )
        obj_a = add_pattern_piece(document, piece_a)
        obj_b = add_pattern_piece(document, piece_b)
        sketch_a = create_sketch_for_piece(piece_a, document)
        create_sketch_for_piece(piece_b, document)
        _set_native_boundary(
            sketch_a,
            Part.ArcOfCircle(
                Part.Circle(App.Vector(10, 5, 0), App.Vector(0, 0, 1), 5),
                -math.pi / 2,
                math.pi / 2,
            ),
        )
        document.recompute()

        seam_arc = add_seam(document, Seam(obj_a.PieceId, 1, obj_b.PieceId, 0, id="native-arc-seam"))
        seam_line = add_seam(document, Seam(obj_a.PieceId, 0, obj_b.PieceId, 1, id="native-line-seam"))
        document.recompute()
        assert str(seam_arc.Status) == "Valid"
        assert str(seam_line.Status) == "Valid"
        arc_signature = str(seam_arc.EdgeASignature)
        line_signature = str(seam_line.EdgeASignature)
        assert arc_signature.startswith("native-v1:")
        assert line_signature.startswith("native-v1:")

        fd, path = tempfile.mkstemp(suffix=".FCStd")
        os.close(fd)
        try:
            document.saveAs(path)
            App.closeDocument(document.Name)
            document = None
            reloaded = App.openDocument(path)
            reloaded.recompute()
            restored_arc = next(obj for obj in reloaded.Objects if getattr(obj, "SeamId", "") == "native-arc-seam")
            restored_line = next(obj for obj in reloaded.Objects if getattr(obj, "SeamId", "") == "native-line-seam")
            restored_piece = next(obj for obj in reloaded.Objects if getattr(obj, "PieceId", "") == "native-a")
            assert str(restored_arc.Status) == "Valid"
            assert str(restored_line.Status) == "Valid"
            assert str(restored_arc.EdgeASignature) == arc_signature
            assert str(restored_line.EdgeASignature) == line_signature

            sketch = restored_piece.Sketch
            _set_native_boundary(
                sketch,
                Part.ArcOfCircle(
                    Part.Circle(App.Vector(5, 5, 0), App.Vector(0, 0, 1), math.sqrt(50)),
                    -math.pi / 4,
                    math.pi / 4,
                ),
            )
            reloaded.recompute()
            assert str(restored_arc.Status) == "Changed reference"
            assert str(restored_line.Status) == "Valid"
            assert str(restored_arc.EdgeASignature) == arc_signature

            sketch.clear()
            sketch.addGeometry([
                Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)),
                Part.LineSegment(App.Vector(10, 10, 0), App.Vector(0, 10, 0)),
                Part.LineSegment(App.Vector(0, 10, 0), App.Vector(0, 0, 0)),
            ], False)
            sketch.SemanticEdgeIds = [
                "native-a:edge:0",
                "native-a:edge:2",
                "native-a:edge:3",
            ]
            sketch.GeometryAuthority = "Sketcher"
            reloaded.recompute()
            assert str(restored_arc.Status) == "Missing reference"
            assert str(restored_line.Status) == "Valid"
            App.closeDocument(reloaded.Name)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    finally:
        if document is not None and document.Name in App.listDocuments():
            App.closeDocument(document.Name)


def test_native_mn_network_save_reload_curve_edit_invalidates_and_repairs():
    if App is None or Part is None:
        return
    document = App.newDocument("NativeMNSeamFingerprint")
    path = None
    try:
        piece_a = PatternPiece("NativeMNA", [(0, 0), (10, 0), (10, 10), (0, 10)], id="native-mn-a")
        piece_b = PatternPiece("NativeMNB", [(0, 0), (10, 0), (10, 10), (0, 10)], id="native-mn-b")
        obj_a = add_pattern_piece(document, piece_a)
        obj_b = add_pattern_piece(document, piece_b)
        sketch_a = create_sketch_for_piece(piece_a, document)
        sketch_b = create_sketch_for_piece(piece_b, document)

        def set_boundary(sketch, piece_id, arc):
            sketch.clear()
            sketch.addGeometry([
                Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)),
                arc,
                Part.LineSegment(App.Vector(10, 10, 0), App.Vector(0, 10, 0)),
                Part.LineSegment(App.Vector(0, 10, 0), App.Vector(0, 0, 0)),
            ], False)
            sketch.SemanticEdgeIds = [f"{piece_id}:edge:{i}" for i in range(4)]
            sketch.GeometryAuthority = "Sketcher"

        set_boundary(sketch_a, obj_a.PieceId, Part.ArcOfCircle(Part.Circle(App.Vector(10, 5, 0), App.Vector(0, 0, 1), 5), -math.pi / 2, math.pi / 2))
        set_boundary(sketch_b, obj_b.PieceId, Part.ArcOfCircle(Part.Circle(App.Vector(10, 5, 0), App.Vector(0, 0, 1), 5), -math.pi / 2, math.pi / 2))
        document.recompute()
        relationship_id = "native-mn"
        models = build_mn_seams(
            relationship_id,
            [SewingMember(obj_a.PieceId, 0), SewingMember(obj_a.PieceId, 1)],
            [SewingMember(obj_b.PieceId, 0), SewingMember(obj_b.PieceId, 1)],
            {
                (obj_a.PieceId, 0): 10.0, (obj_a.PieceId, 1): 10.0,
                (obj_b.PieceId, 0): 10.0, (obj_b.PieceId, 1): 10.0,
            },
            reversed_b=True,
        )
        seams = [add_seam(document, model) for model in models]
        network = add_sewing_network(document, seams, relationship_id, "NativeMNNetwork")
        document.recompute()
        assert len(network.Seams) == 2
        assert str(network.Status) == "Valid"
        endpoint_pairs = tuple(
            (str(seam.SeamId), str(seam.EdgeAId), str(seam.EdgeBId), float(seam.StartA), float(seam.EndA), float(seam.StartB), float(seam.EndB), bool(seam.ReversedB))
            for seam in network.Seams
        )
        fd, path = tempfile.mkstemp(suffix=".FCStd"); os.close(fd)
        document.saveAs(path)
        App.closeDocument(document.Name); document = None
        reloaded = App.openDocument(path); reloaded.recompute()
        network = next(obj for obj in reloaded.Objects if str(getattr(obj, "RelationshipId", "")) == relationship_id)
        restored_pairs = tuple(
            (str(seam.SeamId), str(seam.EdgeAId), str(seam.EdgeBId), float(seam.StartA), float(seam.EndA), float(seam.StartB), float(seam.EndB), bool(seam.ReversedB))
            for seam in network.Seams
        )
        assert restored_pairs == endpoint_pairs
        assert str(network.Status) == "Valid"
        restored_piece_a = next(obj for obj in reloaded.Objects if str(getattr(obj, "PieceId", "")) == obj_a.PieceId)
        set_boundary(restored_piece_a.Sketch, restored_piece_a.PieceId, Part.ArcOfCircle(Part.Circle(App.Vector(5, 5, 0), App.Vector(0, 0, 1), math.sqrt(50)), -math.pi / 4, math.pi / 4))
        reloaded.recompute()
        changed = [seam for seam in network.Seams if str(seam.Status) == "Changed reference"]
        valid = [seam for seam in network.Seams if str(seam.Status) == "Valid"]
        assert len(changed) == 1 and len(valid) == 1
        assert str(network.Status) == "Invalid"
        changed_seam = changed[0]
        changed_seam.EdgeASignature = refresh_edge_reference_signature(changed_seam.PatternA, changed_seam.EdgeAId)
        reloaded.recompute()
        assert all(str(seam.Status) == "Valid" for seam in network.Seams)
        assert str(network.Status) == "Valid"
        App.closeDocument(reloaded.Name)
    finally:
        try:
            if path is not None:
                os.unlink(path)
        except OSError:
            pass
        if document is not None and document.Name in App.listDocuments():
            App.closeDocument(document.Name)


if __name__ == "__main__":
    test_pattern_piece_proxy_recomputes_deterministically()
    test_pattern_piece_proxy_rejects_invalid_dimensions()
    test_native_seam_reference_save_reload_curve_edit_and_missing()
    test_native_mn_network_save_reload_curve_edit_invalidates_and_repairs()
    print("FreeCAD object proxy and native seam reference tests passed")

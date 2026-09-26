from math import isclose

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import (
    average_point,
    minimum_signed_clearance,
    nearest_target_projection,
)


def _top_surface():
    return CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0),
            (10.0, -10.0, 0.0),
            (10.0, 10.0, 0.0),
            (-10.0, 10.0, 0.0),
        ),
        triangles=((0, 1, 2), (0, 2, 3)),
    )


def test_nearest_projection_reports_outward_normal_and_distance():
    surface = _top_surface()
    projection = nearest_target_projection((0.0, 0.0, 5.0), surface)
    assert projection.triangle_index in {0, 1}
    assert isclose(projection.point[2], 0.0)
    assert projection.normal == (0.0, 0.0, 1.0)
    assert isclose(projection.distance, 5.0)


def test_signed_clearance_rejects_points_inside_target():
    surface = _top_surface()
    assert isclose(minimum_signed_clearance(((0.0, 0.0, 4.0),), surface).minimum_signed_clearance, 4.0)
    assert isclose(minimum_signed_clearance(((0.0, 0.0, -4.0),), surface).minimum_signed_clearance, -4.0)


def test_nearest_projection_fails_closed_on_opposing_ambiguous_normals():
    surface = CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (0.0, 10.0, 0.0),
            (-10.0, -10.0, 0.0), (0.0, 10.0, 0.0), (10.0, -10.0, 0.0),
        ),
        triangles=((0, 1, 2), (3, 4, 5)),
    )
    try:
        nearest_target_projection((0.0, 0.0, 5.0), surface)
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("opposing equally-near target normals must fail closed")


def test_average_point_is_deterministic():
    assert average_point(((0.0, 0.0, 2.0), (2.0, 4.0, 4.0))) == (1.0, 2.0, 3.0)


def _freecad_case(piece_xs=(-25.0, 25.0)):
    try:
        import FreeCAD as App
        import Part
    except ImportError:
        return None
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene
    from freecad_cloth.simulation.DrapeTarget import create_drape_target

    doc = App.newDocument("TargetPlacementBehavior")
    source = doc.addObject("Part::Feature", "TargetSource")
    source.Shape = Part.makeBox(100.0, 100.0, 40.0, App.Vector(-50.0, -50.0, 0.0))
    target = create_drape_target(doc, source, "FreeCAD Geometry", 0.5, 0.0)

    scene = create_fitting_scene()
    scene.DrapeTarget = target
    pieces = []
    homes = []
    for index, x in enumerate(piece_xs):
        piece = doc.addObject("Part::Feature", "PatternPiece%d" % index)
        piece.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
        piece.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = "piece-%d" % index
        piece.Shape = Part.makeBox(20.0, 10.0, 1.0)
        piece.Placement = App.Placement(
            App.Vector(x, 0.0, 200.0),
            App.Rotation(App.Vector(0.0, 0.0, 1.0), 17.0 + index),
        )
        sketch = doc.addObject("Part::Feature", "Sketch%d" % index)
        sketch.Shape = Part.makePlane(20.0, 10.0)
        piece.addProperty("App::PropertyLink", "Sketch", "Cloth").Sketch = sketch
        sketch.Placement = piece.Placement
        pieces.append(piece)
        base = piece.Placement.Base
        axis = piece.Placement.Rotation.Axis
        homes.append(
            PiecePlacement(
                str(piece.PieceId),
                (float(base.x), float(base.y), float(base.z)),
                float(piece.Placement.Rotation.Angle),
                (float(axis.x), float(axis.y), float(axis.z)),
            ).to_string()
        )

    scene.PatternPieces = list(pieces)
    scene.PiecePlacements = list(homes)
    scene.HomePlacements = list(homes)
    scene.FitStatus = "Ready"
    doc.recompute()
    return doc, scene, target, tuple(pieces), tuple(homes)


def test_ready_and_negative_drape_target_states_fail_closed():
    try:
        import FreeCAD as App
    except ImportError:
        return
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target, target_status

    case = _freecad_case((0.0,))
    assert case is not None
    doc, scene, target, pieces, homes = case
    try:
        assert target_status(target)["state"] == "ready"
        assert target_status(None)["state"] == "missing"

        target.Enabled = False
        assert target_status(target)["state"] == "disabled"
        target.Enabled = True

        source = target.SourceObject
        source.Placement.Base = App.Vector(1.0, 0.0, 0.0)
        assert target_status(target)["state"] == "stale"
        refresh_drape_target(target)
        assert target_status(target)["state"] == "ready"

        target.CollisionVertexCount = 0
        assert target_status(target)["state"] == "unbuilt"
        refresh_drape_target(target)

        target.TargetType = "NotARealTarget"
        assert target_status(target)["state"] == "invalid"
        target.TargetType = "FreeCAD Geometry"
        refresh_drape_target(target)

        from freecad_cloth.avatar.FittingCommands import snap_pattern_pieces_to_target
        import Part
        second_source = doc.addObject("Part::Feature", "TargetSource2")
        second_source.Shape = Part.makeBox(100.0, 100.0, 40.0, App.Vector(-50.0, -50.0, 0.0))
        second_target = create_drape_target(doc, second_source, "FreeCAD Geometry", 0.5, 0.0)
        scene.DrapeTarget = target
        doc.recompute()
        try:
            snap_pattern_pieces_to_target(pieces, target)
        except ValueError as exc:
            assert "exactly one DrapeTarget" in str(exc)
        else:
            raise AssertionError("multiple DrapeTarget objects must fail closed")
        assert tuple(scene.HomePlacements) == homes
    finally:
        App.closeDocument(doc.Name)


def test_translation_limit_fails_before_mutation():
    case = _freecad_case((0.0,))
    if case is None:
        return
    doc, scene, target, pieces, homes = case
    try:
        from freecad_cloth.avatar.FittingCommands import snap_pattern_pieces_to_target
        before = pieces[0].Placement
        try:
            snap_pattern_pieces_to_target(pieces, target, clearance=2.0, max_translation=1.0)
        except ValueError as exc:
            assert "translation guard" in str(exc)
        else:
            raise AssertionError("a too-small translation bound must fail closed")
        assert pieces[0].Placement == before
        assert tuple(scene.PiecePlacements) == tuple(homes)
        assert tuple(scene.HomePlacements) == tuple(homes)
        assert str(scene.FitStatus) == "Ready"
    finally:
        import FreeCAD as App
        App.closeDocument(doc.Name)


def test_multi_piece_post_transform_failure_rolls_back_everything():
    case = _freecad_case((-25.0, 25.0))
    if case is None:
        return
    doc, scene, target, pieces, homes = case
    try:
        from freecad_cloth.avatar import TargetPlacement
        from freecad_cloth.avatar.FittingCommands import snap_pattern_pieces_to_target

        before_piece = {piece.Name: piece.Placement for piece in pieces}
        before_sketch = {piece.Name: piece.Sketch.Placement for piece in pieces}
        before_persisted = tuple(scene.PiecePlacements)
        before_home = tuple(scene.HomePlacements)
        before_status = str(scene.FitStatus)

        original = TargetPlacement.minimum_signed_clearance
        state = {"forced": False}

        def forced_failure(points, surface):
            report = original(points, surface)
            if not state["forced"]:
                state["forced"] = True
                return TargetPlacement.ClearanceReport(
                    -10000.0, report.point_index, report.point, report.projection
                )
            return report

        TargetPlacement.minimum_signed_clearance = forced_failure
        try:
            snap_pattern_pieces_to_target(pieces, target, clearance=2.0, max_translation=750.0)
        except ValueError as exc:
            assert "cannot satisfy" in str(exc)
        else:
            raise AssertionError("forced post-transform clearance failure must abort the placement")
        finally:
            TargetPlacement.minimum_signed_clearance = original

        assert state["forced"] is True
        for piece in pieces:
            assert piece.Placement == before_piece[piece.Name]
            assert piece.Sketch.Placement == before_sketch[piece.Name]
        assert tuple(scene.PiecePlacements) == before_persisted
        assert tuple(scene.HomePlacements) == before_home
        assert str(scene.FitStatus) == before_status
    finally:
        import FreeCAD as App
        App.closeDocument(doc.Name)


def test_successful_snap_preserves_relative_spacing_and_exact_reset():
    case = _freecad_case((-25.0, 25.0))
    if case is None:
        return
    doc, scene, target, pieces, homes = case
    try:
        from freecad_cloth.avatar.FittingCommands import reset_arrangement, snap_pattern_pieces_to_target
        before_relative = tuple(
            round(float(b.Placement.Base.x - a.Placement.Base.x), 6)
            for a, b in ((pieces[0], pieces[1]),)
        )
        original_placements = {piece.Name: piece.Placement for piece in pieces}
        original_sketch = {piece.Name: piece.Sketch.Placement for piece in pieces}

        result = snap_pattern_pieces_to_target(pieces, target, clearance=2.0, max_translation=750.0)
        assert result["pieces"]
        assert str(scene.FitStatus) == "Target snapped"
        assert tuple(scene.HomePlacements) == homes

        after_relative = tuple(
            round(float(b.Placement.Base.x - a.Placement.Base.x), 6)
            for a, b in ((pieces[0], pieces[1]),)
        )
        assert after_relative == before_relative
        assert any(piece.Placement != original_placements[piece.Name] for piece in pieces)

        reset_arrangement()
        assert str(scene.FitStatus) == "Arrangement reset"
        assert tuple(scene.PiecePlacements) == homes
        assert tuple(scene.HomePlacements) == homes
        for piece in pieces:
            assert piece.Placement == original_placements[piece.Name]
            assert piece.Sketch.Placement == original_sketch[piece.Name]
    finally:
        import FreeCAD as App
        App.closeDocument(doc.Name)

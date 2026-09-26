import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    apply_rigid_delta,
    assert_minimum_surface_clearance,
    require_ready_target_status,
    solve_rigid_z,
    target_surface_anchor
)


def _box_surface():
    vertices = (
        (-10, -10, -10), (10, -10, -10), (10, 10, -10), (-10, 10, -10),
        (-10, -10, 10), (10, -10, 10), (10, 10, 10), (-10, 10, 10),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0),
    )
    return surface_from_triangles(vertices, triangles)


def test_target_surface_anchor_is_deterministic_and_outward():
    surface = _box_surface()
    first = target_surface_anchor(surface, (0, 0, 25), (0, 0, 1))
    second = target_surface_anchor(surface, (0, 0, 25), (0, 0, 1))
    assert first == second
    assert first.point[2] == pytest.approx(10.0)
    assert first.normal == (0.0, 0.0, 1.0)


def test_rigid_solution_is_deterministic_and_bounded():
    source = ((-5, 0, 0), (5, 0, 0))
    target = ((-5, 20, 2), (5, 20, 2))
    delta = solve_rigid_z(source, target, max_translation=100, max_rotation=45)
    assert delta.rotation_z == pytest.approx(0.0)
    assert delta.translation == pytest.approx((0.0, 20.0, 2.0))
    assert apply_rigid_delta(source, delta) == pytest.approx(target)


def test_rigid_solution_fails_closed_on_transform_bound():
    with pytest.raises(TargetPlacementError):
        solve_rigid_z(((0, 0, 0),), ((1000, 0, 0),), max_translation=100, max_rotation=45)


def test_step_zero_clearance_is_enforced_against_authoritative_surface():
    surface = _box_surface()
    assert assert_minimum_surface_clearance(surface, ((0, 0, 18),), 8.0) == pytest.approx(8.0)
    with pytest.raises(TargetPlacementError):
        assert_minimum_surface_clearance(surface, ((0, 0, 11),), 8.0)


def test_stale_or_missing_targets_fail_closed():
    with pytest.raises(TargetPlacementError):
        require_ready_target_status({"state": "stale", "message": "target changed"})
    with pytest.raises(TargetPlacementError):
        require_ready_target_status({"state": "missing", "message": "target missing"})
    with pytest.raises(TargetPlacementError):
        require_ready_target_status(None)


def test_fitting_scene_persists_authoritative_target_and_handoff():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert 'App::PropertyLinkGlobal", "DrapeTarget", "Fitting"' in fitting
    assert 'scene.DrapeTarget = target' in fitting
    assert 'simulation.DrapeTarget = fitting_target' in fitting


def test_target_aware_placement_is_transactional_on_post_transform_failure():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert 'original_placement = piece.Placement' in fitting
    assert 'previous_piece_placements = list(getattr(scene, "PiecePlacements", ()))' in fitting
    assert 'except Exception:' in fitting
    assert 'piece.Placement = original_placement' in fitting
    assert 'scene.PiecePlacements = previous_piece_placements' in fitting
    assert 'scene.FitStatus = previous_fit_status' in fitting


def test_wrap_normals_match_front_back_convention():
    from freecad_cloth.avatar.TargetAwarePlacement import wrap_normal
    assert wrap_normal("front") == (0.0, -1.0, 0.0)
    assert wrap_normal("back") == (0.0, 1.0, 0.0)


def test_rigid_solution_bounds_final_anchor_motion():
    with pytest.raises(TargetPlacementError):
        solve_rigid_z(
            ((100.0, 0.0, 0.0),),
            ((0.0, 0.0, 0.0),),
            max_translation=50.0,
            max_rotation=45.0,
        )


def test_piece_placement_round_trip_preserves_rotation_axis():
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    value = PiecePlacement("piece", (1.0, 2.0, 3.0), 90.0, (1.0, 0.0, 0.0))
    restored = PiecePlacement.from_string(value.to_string())
    assert restored == value


def test_legacy_piece_placement_defaults_to_z_axis():
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    restored = PiecePlacement.from_string("piece|1,2,3|90")
    assert restored.rotation_axis == (0.0, 0.0, 1.0)


def test_target_aware_fitting_command_is_on_fitting_surface():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    commands = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "ClothFitting_TargetAwareArrange" in commands
    assert "target_aware_arrange_selected" in commands
    assert "target_status(target)" in commands
    assert "piece.Placement = original_placement" in commands


def test_target_aware_place_piece_rolls_back_piece_sketch_and_fit_state_on_forced_post_transform_failure():
    try:
        import FreeCAD as App
        import Part
    except ModuleNotFoundError:
        pytest.skip("FreeCAD Python module is unavailable in the non-GUI test runner")
    from unittest.mock import patch
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor, PiecePlacement
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene, target_aware_place_piece
    from freecad_cloth.simulation.DrapeTarget import create_drape_target
    from freecad_cloth.avatar.TargetAwarePlacement import TargetPlacementError

    doc = App.newDocument("TargetAwareRollback")
    try:
        source = doc.addObject("Part::Feature", "TargetSource")
        source.Shape = Part.makeBox(100.0, 100.0, 100.0)
        piece = doc.addObject("Part::Feature", "PatternPiece")
        piece.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
        piece.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = "rollback-piece"
        piece.Shape = Part.makeBox(12.0, 12.0, 1.0)
        sketch = doc.addObject("Part::Feature", "NativeSketch")
        piece.addProperty("App::PropertyLink", "Sketch", "Pattern")
        piece.Sketch = sketch
        original_piece = App.Placement(App.Vector(0.0, 15.0, 25.0), App.Rotation(App.Vector(1, 0, 0), 90.0))
        original_sketch = App.Placement(App.Vector(7.0, 18.0, 30.0), App.Rotation(App.Vector(0, 1, 0), 25.0))
        piece.Placement = original_piece
        sketch.Placement = original_sketch
        target = create_drape_target(doc, source, "FreeCAD Geometry", 0.5, 0.0)
        fitting = create_fitting_scene()
        fitting.DrapeTarget = target
        fitting.PatternPieces = [piece]
        home = PiecePlacement("rollback-piece", (0.0, 15.0, 25.0), 90.0, (1.0, 0.0, 0.0))
        fitting.HomePlacements = [home.to_string()]
        fitting.PiecePlacements = [home.to_string()]
        fitting.FitStatus = "Before transaction"
        anchors = (GarmentAnchor("rollback-piece", "front_anchor", (6.0, 6.0, 0.0), "front"),)
        doc.recompute()
        before_piece = piece.Placement
        before_sketch = sketch.Placement
        before_placements = list(fitting.PiecePlacements)
        before_status = fitting.FitStatus
        with patch(
            "freecad_cloth.avatar.TargetAwarePlacement.assert_minimum_surface_clearance",
            side_effect=TargetPlacementError("forced post-transform validation failure"),
        ):
            with pytest.raises(TargetPlacementError, match="forced post-transform"):
                target_aware_place_piece(piece, target, anchors, clearance=8.0, max_translation=600.0, max_rotation=45.0)
        assert piece.Placement == before_piece
        assert sketch.Placement == before_sketch
        assert list(fitting.PiecePlacements) == before_placements
        assert fitting.FitStatus == before_status
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


def test_create_simulation_from_fitting_propagates_target_and_target_source_signature_is_invalidation_sensitive():
    try:
        import FreeCAD as App
        import Part
    except ModuleNotFoundError:
        pytest.skip("FreeCAD Python module is unavailable in the non-GUI test runner")
    from types import SimpleNamespace
    from unittest.mock import patch
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene, create_simulation_from_fitting
    from freecad_cloth.simulation.DrapeTarget import create_drape_target
    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

    doc = App.newDocument("TargetHandoff")
    try:
        source = doc.addObject("Part::Feature", "TargetSource")
        source.Shape = Part.makeBox(100.0, 100.0, 100.0)
        piece = doc.addObject("App::FeaturePython", "PatternPiece")
        piece.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
        piece.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = "handoff-piece"
        target = create_drape_target(doc, source, "FreeCAD Geometry", 0.5, 0.0)
        fitting = create_fitting_scene()
        fitting.DrapeTarget = target
        fitting.PatternPieces = [piece]
        doc.recompute()
        simulated = SimpleNamespace()
        with patch("freecad_cloth.simulation.SimulationObjects.create_simulation_scene", return_value=simulated):
            result = create_simulation_from_fitting()
        assert result is simulated
        assert result.DrapeTarget is target
        first = _simulation_source_signature(SimpleNamespace(
            Document=doc, DrapeTarget=target, PinMode="None", PinSelection=[], StitchSamples=8,
        ), ())
        source.Placement.Base = App.Vector(5.0, 0.0, 0.0)
        second = _simulation_source_signature(SimpleNamespace(
            Document=doc, DrapeTarget=target, PinMode="None", PinSelection=[], StitchSamples=8,
        ), ())
        assert first != second
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)

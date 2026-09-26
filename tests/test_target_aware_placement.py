import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    apply_rigid_delta,
    assert_minimum_surface_clearance,
    require_ready_target_status,
    solve_rigid_z,
    target_surface_anchor,
    transform_surface,
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



def test_target_aware_placement_transaction_contract():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "original_placement = piece.Placement" in source
    assert "piece_placements_before" in source
    assert "home_placements_before" in source
    assert "garment_anchors_before" in source
    assert "piece.Placement = original_placement" in source
    assert "scene.HomePlacements = list(home_placements_before)" in source
    assert "scene.GarmentAnchors = list(garment_anchors_before)" in source
    assert "pattern_pieces_before = tuple(getattr(scene, "PatternPieces", ()) or ())" in source
    assert "scene.PatternPieces = list(pattern_pieces_before)" in source
    assert "avatar_proxy_before = getattr(scene, "AvatarProxy", None)" in source
    assert "scene.AvatarProxy = avatar_proxy_before" in source


def test_fitting_simulation_handoff_preserves_authoritative_target():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert 'fitting_target = getattr(scene, "DrapeTarget", None)' in source
    assert "simulation.DrapeTarget = fitting_target" in source


def test_target_surface_transform_preserves_world_coordinates_under_non_identity_offset():
    surface = _box_surface()
    transformed = transform_surface(surface, lambda point: (point[0] + 100.0, point[1] - 20.0, point[2] + 5.0))
    hit = target_surface_anchor(transformed, (100.0, -20.0, 25.0), (0.0, 0.0, 1.0))
    assert hit.point == pytest.approx((100.0, -20.0, 15.0))
    assert hit.normal == (0.0, 0.0, 1.0)


def test_target_surface_is_transformed_into_world_frame_before_matching():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "surface = transform_surface(" in source
    assert "source_placement.multVec(App.Vector(*point))" in source

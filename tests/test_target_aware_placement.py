import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    apply_rigid_delta,
    assert_minimum_surface_clearance,
    require_ready_target_status,
    solve_rigid_z,
    target_surface_anchor,
    transform_surface_to_world,
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


def test_target_aware_command_icon_and_ci_evidence_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert (root / "resources" / "icons" / "ClothFitting_TargetAwareArrange.svg").is_file()
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "grep -q 'step-0-target-clearance=' docs/images/generated/gui-progress.log" in workflow
    assert "grep -q 'first-step-target-clearance=' docs/images/generated/gui-progress.log" in workflow
    assert "grep -q 'pin-mode=None solver-pins=0' docs/images/generated/gui-progress.log" in workflow
    assert "cloth-simulation-arranged.png" in workflow


def test_rigid_anchor_transform_preserves_intra_panel_anchor_distance():
    source = ((-20.0, 0.0, 10.0), (20.0, 0.0, 10.0))
    target = ((-15.0, 25.0, 13.0), (15.0, 25.0, 13.0))
    delta = solve_rigid_z(source, target, max_translation=100.0, max_rotation=45.0)
    transformed = apply_rigid_delta(source, delta)
    def distance(a, b):
        return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5
    assert distance(source[0], source[1]) == pytest.approx(distance(transformed[0], transformed[1]))

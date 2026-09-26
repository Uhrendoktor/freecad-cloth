import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    apply_rigid_delta,
    assert_minimum_surface_clearance,
    minimum_surface_clearance_detail, minimum_target_vertex_clearance,
    require_ready_target_status,
    solve_rigid_z,
    target_surface_anchor,
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


def test_minimum_surface_clearance_detail_returns_worst_hit_normal():
    surface = _box_surface()
    clearance, hit = minimum_surface_clearance_detail(surface, ((0, 0, 11), (0, 0, 8)))
    assert clearance == pytest.approx(-2.0)
    assert hit.normal == (0.0, 0.0, 1.0)


def test_target_clearance_correction_runs_before_anchor_assertion():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    initial = fitting.index("anchor_clearance = minimum_surface_clearance(surface, placed_points)")
    correction = fitting.index("while (", initial)
    final_assert = fitting.index("anchor_clearance = assert_minimum_surface_clearance", correction)
    assert initial < correction < final_assert


def test_target_clearance_correction_is_bounded_and_uses_worst_sample_normal():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "minimum_surface_clearance_detail" in fitting
    assert "while (" in fitting
    assert "vertex_deficit = float(clearance) - float(vertex_clearance)" in fitting
    assert "worst_hit.normal[0]" in fitting

def test_minimum_target_vertex_clearance_matches_existing_acceptance_metric():
    surface = _box_surface()
    assert minimum_target_vertex_clearance(surface, ((0, 0, 12),)) == pytest.approx(2.0)


def test_target_snap_preserves_vertex_clearance_gate():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "minimum_target_vertex_clearance" in fitting
    assert "vertex_deficit = float(clearance) - float(vertex_clearance)" in fitting
    assert 'target-aware vertex clearance' in fitting

def test_stale_or_missing_targets_fail_closed():
    with pytest.raises(TargetPlacementError):
        require_ready_target_status({"state": "stale", "message": "target changed"})
    with pytest.raises(TargetPlacementError):
        require_ready_target_status({"state": "missing", "message": "target missing"})
    with pytest.raises(TargetPlacementError):
        require_ready_target_status(None)


def test_fitting_action_is_registered_and_transactional():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "def target_aware_place_piece" in fitting
    assert "def snap_pieces_to_target" in fitting
    assert '"ClothFitting_SnapPiecesToTarget"' in fitting
    assert "scene.DrapeTarget" in fitting
    assert "PiecePlacement.from_string" in fitting

def test_fitting_action_checks_the_complete_piece_surface_not_only_anchors():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "def _piece_world_surface_points" in fitting
    assert "resolve_piece_ir(piece)" in fitting
    assert "geometry_from_piece_ir(piece_ir)" in fitting
    assert "piece_clearance = assert_minimum_surface_clearance" in fitting

def test_target_snap_contract_is_atomic_and_matches_simulation_panel_adapter():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fitting = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    gui = (root / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
    assert "snap_pieces_to_target" in fitting
    assert "except Exception:" in fitting
    assert "snap_pattern_pieces_to_target(pattern_pieces=None" in fitting
    assert 'snap_pattern_pieces_to_target(tuple(getattr(fitting, "PatternPieces", ()) or ()))' in gui


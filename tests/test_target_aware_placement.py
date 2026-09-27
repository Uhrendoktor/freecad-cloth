import math

import pytest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.AvatarFitting import FittingScene, GarmentAnchor, PiecePlacement
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    apply_rigid_delta,
    anchor_clearance,
    solve_rigid_z,
    target_surface_anchor,
    wrap_normal,
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


def test_wrap_normals_are_stable():
    assert wrap_normal("front") == (0.0, 1.0, 0.0)
    assert wrap_normal("back") == (0.0, -1.0, 0.0)


def test_target_surface_anchor_is_deterministic_and_outward():
    surface = _box_surface()
    first = target_surface_anchor(surface, (0, 25, 0), wrap_normal("front"))
    second = target_surface_anchor(surface, (0, 25, 0), wrap_normal("front"))
    assert first == second
    assert first.point[1] == pytest.approx(10.0)
    assert first.normal == (0.0, 1.0, 0.0)


def test_shared_rigid_solution_preserves_pairwise_distance():
    source = ((-5, 0, 0), (5, 0, 0), (0, 4, 2))
    target = ((-5, 20, 2), (5, 20, 2), (0, 24, 4))
    delta = solve_rigid_z(source, target, max_translation=100, max_rotation=45)
    transformed = apply_rigid_delta(source, delta)
    source_pair = math.dist(source[0], source[1])
    transformed_pair = math.dist(transformed[0], transformed[1])
    assert transformed_pair == pytest.approx(source_pair)
    assert delta.translation == pytest.approx((0.0, 20.0, 2.0))
    assert delta.rotation_z == pytest.approx(0.0)


def test_shared_rigid_solution_preserves_relative_rotation():
    source = ((-5, 0, 0), (5, 0, 0))
    angle = math.radians(20.0)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    target = tuple(
        (cos_a * p[0] - sin_a * p[1] + 15.0, sin_a * p[0] + cos_a * p[1] - 7.0, p[2] + 3.0)
        for p in source
    )
    delta = solve_rigid_z(source, target, max_translation=100, max_rotation=45)
    transformed = apply_rigid_delta(source, delta)
    assert delta.rotation_z == pytest.approx(20.0)
    assert transformed == pytest.approx(target)
    source_vector = (source[1][0] - source[0][0], source[1][1] - source[0][1])
    transformed_vector = (transformed[1][0] - transformed[0][0], transformed[1][1] - transformed[0][1])
    assert math.degrees(math.atan2(transformed_vector[1], transformed_vector[0]) - math.atan2(source_vector[1], source_vector[0])) == pytest.approx(20.0)


def test_shared_rigid_solution_fails_closed_on_bounds():
    with pytest.raises(TargetPlacementError):
        solve_rigid_z(((0, 0, 0), (10, 0, 0)), ((1000, 0, 0), (1010, 0, 0)), max_translation=100, max_rotation=45)


def test_anchor_clearance_is_signed_against_authoritative_normal():
    surface = _box_surface()
    assert anchor_clearance(surface, (0, 18, 0), wrap_normal("front")) == pytest.approx(8.0)
    assert anchor_clearance(surface, (0, 5, 0), wrap_normal("front")) < 0.0


def test_piece_placement_roundtrip_accepts_legacy_and_persists_axis():
    legacy = PiecePlacement.from_string("front|1,2,3|90")
    assert legacy.rotation_axis == (0.0, 0.0, 1.0)
    placement = PiecePlacement("front", (1, 2, 3), 90, (1, 0, 0))
    assert PiecePlacement.from_string(placement.to_string()) == placement


def test_garment_anchors_persist_deterministically():
    anchor = GarmentAnchor("front", "shoulder", (10, 20, 0), "front")
    scene = FittingScene(pieces=(PiecePlacement("front"),), garment_anchors=(anchor,))
    restored = FittingScene.from_json(scene.to_json())
    assert restored == scene
    assert restored.garment_anchors[0].to_string() == "front|shoulder|10,20,0|front"


def test_target_snap_contract_uses_one_shared_transform():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "def snap_pieces_to_target" in source
    assert "solve_rigid_z(" in source
    assert source.count("piece.Placement = updated") == 1
    assert "for piece in pieces:" in source
    assert "scene.FitStatus = \"Target-aware placement applied\"" in source
    assert "except Exception:" in source
    assert "scene.PiecePlacements = previous_piece_placements" in source


def test_target_snap_adapter_is_registered_and_ui_icon_exists():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    icon = root / "resources" / "icons" / "ClothFitting_SnapPiecesToTarget.svg"
    assert '"ClothFitting_SnapPiecesToTarget"' in source
    assert "def snap_pattern_pieces_to_target" in source
    assert "import FreeCAD as App" in source[source.index("def snap_pattern_pieces_to_target"):]
    assert icon.is_file()

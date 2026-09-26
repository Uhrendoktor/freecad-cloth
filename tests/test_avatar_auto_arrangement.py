from freecad_cloth.avatar.AutoArrangement import arrange_piece_centers, target_envelope
from freecad_cloth.avatar.AvatarFitting import PiecePlacement


def test_target_envelope_uses_authored_landmarks():
    target = target_envelope((-450, 450, -80, 240, 0, 1750), shoulder_z=1325, hip_z=820)
    assert target.center_x == 0
    assert target.center_y == 80
    assert target.center_z == 1072.5


def test_named_front_back_panels_release_outside_target():
    target = target_envelope((-450, 450, -80, 240, 0, 1750), shoulder_z=1325, hip_z=820)
    arranged = arrange_piece_centers(
        (
            ("TunicFront", (0.0, 400.0, 950.0)),
            ("TunicBack", (0.0, -200.0, 950.0)),
        ),
        target,
        clearance=10,
    )
    assert arranged["TunicFront"] == (0.0, 250.0, 1072.5)
    assert arranged["TunicBack"] == (0.0, -90.0, 1072.5)


def test_unnamed_piece_preserves_existing_side_intent():
    target = target_envelope((-450, 450, -80, 240, 0, 1750))
    arranged = arrange_piece_centers(
        (("panel-a", (0.0, -200.0, 900.0)),),
        target,
        clearance=8,
    )
    assert arranged["panel-a"][1] == -88.0


def test_piece_placement_backward_compatible_with_extended_rotation():
    legacy = PiecePlacement("piece", (1, 2, 3), 15.0)
    assert PiecePlacement.from_string(legacy.to_string()) == legacy
    upright = PiecePlacement("piece", (1, 2, 3), 0.0, (1.0, 0.0, 0.0), 90.0)
    assert PiecePlacement.from_string(upright.to_string()) == upright

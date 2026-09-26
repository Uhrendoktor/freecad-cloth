from freecad_cloth.avatar.AvatarFitting import ArrangementPoint, garment_arrangement_pose


def test_garment_arrangement_pose_keeps_front_and_back_outside_avatar_bounds():
    point = ArrangementPoint("chest", 0.0, 0.0, 980.0, "front")
    bounds = (-300.0, 300.0, -120.0, 120.0, 0.0, 1700.0)
    front = garment_arrangement_pose(point, bounds, 500.0, 700.0, 5.0)
    back = garment_arrangement_pose(
        ArrangementPoint("chest", 0.0, 0.0, 980.0, "back"),
        bounds,
        500.0,
        700.0,
        5.0,
    )
    assert front[0:3] == (-250.0, 125.0, 630.0)
    assert back[0:3] == (-250.0, -125.0, 630.0)
    assert front[3] == 0.0
    assert back[3] == 180.0


def test_garment_arrangement_pose_rejects_invalid_wrap_direction():
    point = ArrangementPoint("chest", 0.0, 0.0, 980.0, "diagonal")
    try:
        garment_arrangement_pose(point, (-1, 1, -1, 1, 0, 2), 1, 1, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid wrap direction must fail closed")

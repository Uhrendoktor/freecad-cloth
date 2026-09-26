from math import isclose
from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import average_point, minimum_signed_clearance, nearest_target_projection


def _top_surface():
    return CollisionSurface(
        vertices=((-10.0,-10.0,0.0),(10.0,-10.0,0.0),(10.0,10.0,0.0),(-10.0,10.0,0.0)),
        triangles=((0,1,2),(0,2,3)),
    )


def test_nearest_projection_reports_outward_normal_and_distance():
    projection = nearest_target_projection((0.0,0.0,5.0), _top_surface())
    assert projection.triangle_index in {0,1}
    assert isclose(projection.point[2],0.0)
    assert projection.normal == (0.0,0.0,1.0)
    assert isclose(projection.distance,5.0)


def test_signed_clearance_rejects_points_inside_target():
    surface = _top_surface()
    assert isclose(minimum_signed_clearance(((0.0,0.0,4.0),),surface).minimum_signed_clearance,4.0)
    assert isclose(minimum_signed_clearance(((0.0,0.0,-4.0),),surface).minimum_signed_clearance,-4.0)


def test_nearest_projection_fails_closed_on_opposing_ambiguous_normals():
    surface = CollisionSurface(
        vertices=((-10,-10,0),(10,-10,0),(0,10,0),(-10,-10,0),(0,10,0),(10,-10,0)),
        triangles=((0,1,2),(3,4,5)),
    )
    try:
        nearest_target_projection((0.0,0.0,5.0),surface)
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("opposing equally-near target normals must fail closed")


def test_average_point_is_deterministic():
    assert average_point(((0.0,0.0,2.0),(2.0,4.0,4.0))) == (1.0,2.0,3.0)

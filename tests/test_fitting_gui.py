"""Regression coverage for the direct-manipulation fitting frontend."""

from types import SimpleNamespace

from freecad_cloth.avatar.FittingCommands import (
    _geometry_round,
    _mesh_anchor_local_position,
    _target_signature,
    arrangement_anchor_status,
)
from freecad_cloth.avatar.FittingGui import (
    arrangement_rotation,
    coin_position_to_screen,
    nearest_arrangement_point,
)


def test_nearest_arrangement_point_returns_closest_candidate_within_threshold():
    points = (
        SimpleNamespace(X=0.0, Y=0.0, RotationZ=0.0, WrapDirection="front"),
        SimpleNamespace(X=10.0, Y=0.0, RotationZ=15.0, WrapDirection="back"),
    )

    assert nearest_arrangement_point((8.0, 1.0), points, 3.0) is points[1]
    assert nearest_arrangement_point((20.0, 0.0), points, 3.0) is None


def test_nearest_arrangement_point_prefers_closest_even_when_input_is_unsorted():
    points = (
        SimpleNamespace(X=1.0, Y=1.0),
        SimpleNamespace(X=4.0, Y=4.0),
        SimpleNamespace(X=9.0, Y=9.0),
    )

    assert nearest_arrangement_point((3.0, 3.0), points, 5.0) is points[1]


def test_arrangement_rotation_maps_wrap_direction_to_viewport_rotation():
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="front")) == 5.0
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="back")) == 185.0
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="left")) == 95.0
    assert arrangement_rotation(SimpleNamespace(RotationZ=5.0, WrapDirection="right")) == -85.0


def test_coin_event_coordinates_are_converted_before_snap_matching():
    screen_position = coin_position_to_screen((710.0, 461.0), 590.0)
    assert screen_position == (710.0, 129.0)

    target = SimpleNamespace(X=710.0, Y=129.0)
    assert nearest_arrangement_point(screen_position, (target,), 36.0) is target


def test_coordinate_based_arrangement_point_has_no_surface_anchor_requirement():
    from types import SimpleNamespace

    point = SimpleNamespace(AnchorGeometrySignature="", AnchorTarget=None)
    assert arrangement_anchor_status(point) == "unanchored"


def test_surface_anchor_without_its_target_is_not_current():
    from types import SimpleNamespace

    point = SimpleNamespace(AnchorGeometrySignature="saved-signature", AnchorTarget=None)
    assert arrangement_anchor_status(point) == "missing target"


def test_surface_anchor_is_invalidated_when_fitting_target_changes():
    from types import SimpleNamespace

    old_target = SimpleNamespace(Name="OldMannequin")
    new_target = SimpleNamespace(Name="ReplacementMannequin")
    scene = SimpleNamespace(FittingType="FittingScene", AvatarProxy=new_target)
    document = SimpleNamespace(
        Objects=[scene],
        getObject=lambda name: None,
    )
    point = SimpleNamespace(
        AnchorGeometrySignature="previous-geometry-signature",
        AnchorTarget=old_target,
        Document=document,
    )

    assert arrangement_anchor_status(point) == "wrong target"


def test_mesh_anchor_follows_vertex_deformation_when_topology_is_stable():
    from types import SimpleNamespace

    triangles = ((0, 1, 2),)
    target = SimpleNamespace(
        Mesh=SimpleNamespace(
            Topology=(
                ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                triangles,
            )
        )
    )
    anchor = {
        "triangle_index": 0,
        "barycentric": (0.2, 0.3, 0.5),
        "local_point": (0.3, 0.5, 0.0),
    }

    signature_before = _target_signature(target)
    assert _mesh_anchor_local_position(target, anchor) == (0.3, 0.5, 0.0)

    target.Mesh.Topology = (
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 1.0)),
        triangles,
    )

    assert _target_signature(target) == signature_before
    assert _mesh_anchor_local_position(target, anchor) == (0.6, 1.0, 0.5)


def test_mesh_anchor_signature_changes_when_triangle_connectivity_changes():
    from types import SimpleNamespace

    target = SimpleNamespace(
        Mesh=SimpleNamespace(
            Topology=(
                ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                ((0, 1, 2),),
            )
        )
    )
    signature_before = _target_signature(target)
    target.Mesh.Topology = (
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 2, 1),),
    )

    assert _target_signature(target) != signature_before


def test_shape_anchor_signature_canonicalizes_signed_zero():
    assert repr(_geometry_round(-0.0)) == repr(0.0)
    assert repr(_geometry_round(-1e-7)) == repr(0.0)
    assert _geometry_round(1.234567) == 1.23457

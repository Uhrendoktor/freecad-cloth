"""Contracts for the library-backed avatar body model."""

from freecad_cloth.avatar.AnnyAvatarBackend import (
    _BREAST_SHAPE_MEASUREMENT_FIELDS,
    MEASUREMENT_FIELDS,
    _adapt_clad_body_pose_alias,
    _initial_phenotypes,
    _measurement_local_change_labels,
    build_avatar_rig_vertices,
    build_avatar_shape_mesh,
)
from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BODY_VERTEX_COUNT,
    _bone_source_endpoints,
    load_makehuman_skeleton,
)


def test_cloth_gender_slider_is_translated_to_anny_convention() -> None:
    feminine = _initial_phenotypes(gender=0.0, breast_size=0.25)
    masculine = _initial_phenotypes(gender=1.0, breast_size=0.75)

    assert feminine["gender"] == 1.0
    assert masculine["gender"] == 0.0
    assert feminine["cupsize"] == 0.25
    assert masculine["cupsize"] == 0.75
    assert feminine["_local_changes"]["breast-volume-vert-up"] == 0.0
    assert masculine["_local_changes"]["breast-volume-vert-up"] == 0.0


def test_breast_shape_controls_do_not_get_fitted_away_by_bust_measurements() -> None:
    # Bust and underbust remain user measurements, but fitting them as fixed
    # constraints can counteract the independently exposed Anny cupsize shape.
    assert frozenset({"chest", "underbust"}) == _BREAST_SHAPE_MEASUREMENT_FIELDS


def test_shape_controls_are_not_mixed_into_anthropometric_measurements() -> None:
    phenotype = _initial_phenotypes(0.5, 0.5)
    scalar_controls = [value for value in phenotype.values() if isinstance(value, float)]
    assert all(0.0 <= value <= 1.0 for value in scalar_controls)
    assert len({name for name, _measurement in MEASUREMENT_FIELDS}) == len(MEASUREMENT_FIELDS)
    assert len({measurement for _name, measurement in MEASUREMENT_FIELDS}) == len(
        MEASUREMENT_FIELDS
    )


def test_selected_local_morphs_exist_in_installed_anny_assets() -> None:
    labels = _measurement_local_change_labels()

    assert "breast-volume-vert-up" in labels
    assert any("measure-waist-circ" in label for label in labels)
    assert any("measure-bust-circ" in label for label in labels)
    assert any("measure-hips-circ" in label for label in labels)


def test_clad_body_legacy_pose_alias_is_translated_for_anny_forward() -> None:
    class FakeModel:
        def forward(self, *, pose_parameterization: str) -> str:
            return pose_parameterization

    model = FakeModel()
    _adapt_clad_body_pose_alias(model)

    assert model.forward(pose_parameterization="root_relative_world") == "local-bone"
    assert model.forward(pose_parameterization="local-bone") == "local-bone"


def test_hip_only_shape_edits_do_not_change_rig_vertex_space() -> None:
    parameters = AvatarParameters()
    hip_changed = parameters.with_measurements(hip=parameters.measurement("hip") + 120.0)

    assert build_avatar_rig_vertices(parameters) == build_avatar_rig_vertices(hip_changed)


def test_fitted_rig_keeps_helper_vertices_without_exposing_them_as_body_surface() -> None:
    parameters = AvatarParameters()
    rig_vertices = build_avatar_rig_vertices(parameters)
    body_mesh = build_avatar_shape_mesh(parameters, include_skin_offset=False)
    skeleton = load_makehuman_skeleton()

    assert len(body_mesh.vertices) == MAKEHUMAN_BODY_VERTEX_COUNT
    assert len(rig_vertices) > len(body_mesh.vertices)
    referenced_indices = {
        index
        for bone in skeleton["bones"].values()
        for joint_name in (bone["head"], bone["tail"])
        for index in skeleton["joints"][joint_name]
    }
    assert any(index >= MAKEHUMAN_BODY_VERTEX_COUNT for index in referenced_indices)
    for bone_name in skeleton["bones"]:
        _bone_source_endpoints(rig_vertices, skeleton, bone_name)

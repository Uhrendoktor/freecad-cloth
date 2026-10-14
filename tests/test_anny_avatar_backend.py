"""Contracts for the library-backed avatar body model."""

from freecad_cloth.avatar.AnnyAvatarBackend import (
    _BREAST_SHAPE_MEASUREMENT_FIELDS,
    MEASUREMENT_FIELDS,
    _adapt_clad_body_pose_alias,
    _apply_front_breast_fullness,
    _canonicalize_anny_vertices,
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


def test_bust_measurements_are_separated_from_global_phenotype_fit() -> None:
    # Fit chest and underbust through local circumference morphs at neutral
    # cupsize, then restore cupsize so the two independent controls do not cancel.
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


def test_hip_fitting_keeps_the_pre_hip_mesh_origin() -> None:
    import numpy as np

    reference = np.asarray(
        (
            (-0.8, 3.0, 0.0),
            (0.8, 3.0, 0.0),
            (-0.8, 2.0, 0.0),
            (0.8, 2.0, 0.0),
            (-1.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        ),
        dtype=np.float32,
    )
    hip_fitted = reference.copy()
    hip_fitted[4, 0] = -1.8

    baseline, _ = _canonicalize_anny_vertices(reference, reference)
    recentered, _ = _canonicalize_anny_vertices(hip_fitted, hip_fitted)
    stable, _ = _canonicalize_anny_vertices(hip_fitted, reference)

    # The edited hip changes the fitted bounds, but head/torso coordinates must
    # stay fixed in the original frame instead of following the new XY center.
    assert np.array_equal(stable[:4], baseline[:4])
    assert np.max(np.abs(recentered[:4] - baseline[:4])) > 0.1
    assert not np.array_equal(stable[4], baseline[4])


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


def test_front_breast_fullness_moves_only_the_visible_anterior_chest() -> None:
    height_mm = 1750.0
    baseline = (
        (-72.0, 150.0, 0.685 * height_mm),
        (72.0, 150.0, 0.685 * height_mm),
        (-72.0, 150.0, 0.45 * height_mm),
        (250.0, 150.0, 0.685 * height_mm),
        (72.0, -30.0, 0.685 * height_mm),
    )

    neutral = _apply_front_breast_fullness(baseline, 0.0, height_mm)
    fuller = _apply_front_breast_fullness(baseline, 0.65, height_mm)

    assert neutral == baseline
    assert len(fuller) == len(baseline)
    assert fuller[0][1] - baseline[0][1] > 1.0
    assert fuller[1][1] - baseline[1][1] > 1.0
    assert fuller[0][1] == fuller[1][1]
    assert fuller[0][0] == baseline[0][0] and fuller[0][2] == baseline[0][2]
    assert fuller[1][0] == baseline[1][0] and fuller[1][2] == baseline[1][2]
    assert fuller[2] == baseline[2]
    assert fuller[3] == baseline[3]
    assert fuller[4] == baseline[4]

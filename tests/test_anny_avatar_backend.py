"""Contracts for the library-backed avatar body model."""

from freecad_cloth.avatar.AnnyAvatarBackend import (
    MEASUREMENT_FIELDS,
    _initial_phenotypes,
    _measurement_local_change_labels,
)


def test_cloth_gender_slider_is_translated_to_anny_convention():
    feminine = _initial_phenotypes(gender=0.0, breast_size=0.25)
    masculine = _initial_phenotypes(gender=1.0, breast_size=0.75)

    assert feminine["gender"] == 1.0
    assert masculine["gender"] == 0.0
    assert feminine["_local_changes"]["breast-volume-vert-up"] == 0.25
    assert masculine["_local_changes"]["breast-volume-vert-up"] == 0.75


def test_shape_controls_are_not_mixed_into_anthropometric_measurements():
    assert all(0.0 <= value <= 1.0 for value in _initial_phenotypes(0.5, 0.5).values()
               if isinstance(value, float))
    assert len({name for name, _measurement in MEASUREMENT_FIELDS}) == len(MEASUREMENT_FIELDS)
    assert len({measurement for _name, measurement in MEASUREMENT_FIELDS}) == len(
        MEASUREMENT_FIELDS
    )


def test_selected_local_morphs_exist_in_installed_anny_assets():
    labels = _measurement_local_change_labels()

    assert "breast-volume-vert-up" in labels
    assert any("measure-waist-circ" in label for label in labels)
    assert any("measure-bust-circ" in label for label in labels)
    assert any("measure-hips-circ" in label for label in labels)

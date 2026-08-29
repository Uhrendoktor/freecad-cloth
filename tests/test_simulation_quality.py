import pytest

from SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset, solver_parameters


def test_quality_presets_are_monotonic_and_distinct():
    assert set(QUALITY_PRESETS) == {"Fast", "Balanced", "Final"}
    assert preset("Fast").particle_distance > preset("Balanced").particle_distance > preset("Final").particle_distance
    assert preset("Fast").solver_iterations < preset("Final").solver_iterations


def test_material_defaults_and_solver_parameters():
    material = FabricMaterial()
    params = solver_parameters(preset("Final"), material)
    assert params["particle_distance"] == 2.0
    assert params["iterations"] == 16
    assert params["substeps"] == 2
    assert params["density_g_m2"] == 150.0
    assert params["thickness_mm"] == 0.5


@pytest.mark.parametrize("field,value", [("density_g_m2", 0), ("thickness_mm", 0), ("stretch", 1.1), ("shear", -0.1), ("bend", 2), ("friction", -1)])
def test_material_validation_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        FabricMaterial(**{field: value}).validate()


def test_unknown_quality_rejected():
    with pytest.raises(ValueError):
        preset("Ultra")

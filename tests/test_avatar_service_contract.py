# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression coverage for the solver-neutral avatar service contract."""

import pytest

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.AvatarService import AvatarService, _validate_avatar_parameters
from tests.support.assertions import require


def test_avatar_parameter_runtime_guard_preserves_constructor_boundary() -> None:
    """Recognize canonical avatar parameters and reject unrelated runtime values."""
    expected_parameters = AvatarParameters()
    valid_parameters, parameters = _validate_avatar_parameters(expected_parameters)
    valid_text, text_value = _validate_avatar_parameters("not-avatar-parameters")
    require(
        condition=valid_parameters and parameters is expected_parameters,
        message="Canonical AvatarParameters values must pass the service guard.",
    )
    require(
        condition=not valid_text and text_value == "not-avatar-parameters",
        message="Unrelated runtime values must fail the service guard.",
    )


def test_avatar_service_reports_missing_measurements_as_key_errors() -> None:
    """Preserve the canonical missing-measurement error at the service boundary."""
    service = AvatarService()
    with pytest.raises(KeyError, match="missing-measurement"):
        service.measurement("missing-measurement")

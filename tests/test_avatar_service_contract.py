# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression coverage for the solver-neutral avatar service contract."""

from typing import cast

import pytest

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.AvatarService import AvatarService
from tests.support.assertions import require


def test_avatar_parameter_runtime_guard_preserves_constructor_boundary() -> None:
    """Recognize canonical avatar parameters and reject unrelated runtime values."""
    expected_parameters = AvatarParameters()
    service = AvatarService(expected_parameters)
    require(
        condition=service.parameters() is expected_parameters,
        message="AvatarService must retain the canonical AvatarParameters instance.",
    )

    invalid_parameters = cast(AvatarParameters, "not-avatar-parameters")
    with pytest.raises(TypeError, match="AvatarService requires AvatarParameters"):
        AvatarService(invalid_parameters)


def test_avatar_service_reports_missing_measurements_as_key_errors() -> None:
    """Preserve the canonical missing-measurement error at the service boundary."""
    service = AvatarService()
    with pytest.raises(KeyError, match="missing-measurement"):
        service.measurement("missing-measurement")

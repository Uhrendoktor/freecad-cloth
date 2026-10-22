# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for FreeCAD API adapters and legacy avatar pose migration."""

import json
from collections.abc import Callable
from importlib import import_module
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

from support.assertions import require

_avatar_commands = import_module("freecad_cloth.avatar.avatar_commands")


def _private_adapter(name: str) -> Callable[..., object]:
    """Return a private FreeCAD adapter by name for focused regression tests.

    Args:
        name: Attribute name of the adapter to retrieve.

    Raises:
        TypeError: If the attribute is not callable.

    Returns:
        Callable[..., object]: The requested adapter.
    """
    adapter = getattr(_avatar_commands, name)
    if not callable(adapter):
        message = f"Avatar adapter {name!r} is not callable"
        raise TypeError(message)
    return cast("Callable[..., object]", adapter)


_add_feature_property = cast(
    "Callable[[object, str, str, str], object]",
    _private_adapter("_add_feature_property"),
)
_application_new_document = cast(
    "Callable[[object, str], object]",
    _private_adapter("_application_new_document"),
)
_document_add_object = cast(
    "Callable[[object, str, str], object]",
    _private_adapter("_document_add_object"),
)
_document_get_object = cast(
    "Callable[[object, str], object | None]",
    _private_adapter("_document_get_object"),
)
_legacy_pose_data = cast(
    "Callable[[str], dict[str, object] | None]",
    _private_adapter("_legacy_pose_data"),
)
_migrate_legacy_pose_angles = cast(
    "Callable[[str, str, dict[str, float]], None]",
    _private_adapter("_migrate_legacy_pose_angles"),
)

LEGACY_SCHEMA_VERSION: int = 1
CURRENT_SCHEMA_VERSION: int = 4
LEGACY_ARM_ANGLE: float = 12.0
STANDING_ARM_ANGLE: float = 70.0
LEGACY_SKIN_OFFSET: float = 0.0


def test_runtime_adapters_preserve_the_freecad_api_spelling() -> None:
    """Preserve dynamic FreeCAD method calls while exposing typed Python helpers."""
    feature = SimpleNamespace()
    document = SimpleNamespace(
        addObject=Mock(return_value=feature),
        getObject=Mock(return_value=feature),
    )
    application = SimpleNamespace(newDocument=Mock(return_value=document))
    feature.addProperty = Mock(return_value=None)

    created = _document_add_object(
        cast("object", document),
        "Mesh::Feature",
        "ClothAvatar",
    )
    found = _document_get_object(cast("object", document), "DrapeTarget")
    _add_feature_property(
        cast("object", feature),
        "App::PropertyString",
        "AvatarType",
        "Avatar",
    )
    new_document = _application_new_document(
        cast("object", application),
        "ClothSewing",
    )

    require(
        condition=created is feature and found is feature and new_document is document,
        message="FreeCAD adapter helpers must return the objects exposed by the runtime API",
    )
    require(
        condition=document.addObject.call_args.args == ("Mesh::Feature", "ClothAvatar"),
        message="Object creation must preserve the FreeCAD type and name arguments",
    )
    require(
        condition=document.getObject.call_args.args == ("DrapeTarget",),
        message="Object lookup must preserve the requested internal document name",
    )
    require(
        condition=feature.addProperty.call_args.args
        == ("App::PropertyString", "AvatarType", "Avatar"),
        message="Property creation must preserve the FreeCAD property contract",
    )
    require(
        condition=application.newDocument.call_args.args == ("ClothSewing",),
        message="Document creation must preserve the requested internal name",
    )


def test_legacy_pose_loader_only_accepts_schema_one_payloads() -> None:
    """Keep legacy detection restricted to schema one and preserve arm-angle defaults."""
    payload = json.dumps(
        {
            "schema_version": LEGACY_SCHEMA_VERSION,
            "units": "mm",
            "measurements": {},
            "skin_offset": LEGACY_SKIN_OFFSET,
            "pose": {
                "preset": "standing",
                "left_arm_angle": LEGACY_ARM_ANGLE,
                "right_arm_angle": LEGACY_ARM_ANGLE,
            },
        }
    )
    pose_data = _legacy_pose_data(payload)
    require(
        condition=pose_data
        == {
            "preset": "standing",
            "left_arm_angle": LEGACY_ARM_ANGLE,
            "right_arm_angle": LEGACY_ARM_ANGLE,
        },
        message="Schema-one payloads must expose their serialized pose mapping",
    )

    angles = {
        "left_arm_angle": LEGACY_ARM_ANGLE,
        "right_arm_angle": LEGACY_ARM_ANGLE,
    }
    _migrate_legacy_pose_angles(payload, "standing", angles)
    require(
        condition=angles
        == {
            "left_arm_angle": STANDING_ARM_ANGLE,
            "right_arm_angle": STANDING_ARM_ANGLE,
        },
        message="Legacy sentinel angles must migrate to the standing preset defaults",
    )

    newer_payload = json.dumps(
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "pose": {
                "preset": "standing",
                "left_arm_angle": LEGACY_ARM_ANGLE,
                "right_arm_angle": LEGACY_ARM_ANGLE,
            },
        }
    )
    require(
        condition=_legacy_pose_data(newer_payload) is None,
        message="Current-schema payloads must not be treated as legacy migration inputs",
    )

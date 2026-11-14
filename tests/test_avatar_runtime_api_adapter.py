# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for FreeCAD API adapters and legacy avatar pose migration."""

import json
from collections.abc import Callable
from importlib import import_module
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import Mock

from freecad_cloth.avatar.AvatarCommands import (
    JsonObject,
    _AvatarFeature,
    _FreeCADApplication,
    _FreeCADDocument,
)

_avatar_commands = import_module("freecad_cloth.avatar.avatar_commands")


class _AvatarCommandsModule(Protocol):
    """Typed private adapter exports consumed by focused runtime tests."""

    _add_feature_property: Callable[[_AvatarFeature, str, str, str], None]
    _application_new_document: Callable[[_FreeCADApplication, str], _FreeCADDocument]
    _document_add_object: Callable[[_FreeCADDocument, str, str], _AvatarFeature]
    _document_get_object: Callable[[_FreeCADDocument, str], _AvatarFeature | None]
    _legacy_pose_data: Callable[[str], JsonObject | None]
    _migrate_legacy_pose_angles: Callable[[str, str, dict[str, float]], None]


_commands = cast("_AvatarCommandsModule", _avatar_commands)
_add_feature_property = _commands._add_feature_property
_application_new_document = _commands._application_new_document
_document_add_object = _commands._document_add_object
_document_get_object = _commands._document_get_object
_legacy_pose_data = _commands._legacy_pose_data
_migrate_legacy_pose_angles = _commands._migrate_legacy_pose_angles

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
        cast("_FreeCADDocument", document),
        "Mesh::Feature",
        "ClothAvatar",
    )
    found = _document_get_object(cast("_FreeCADDocument", document), "DrapeTarget")
    _add_feature_property(
        cast("_AvatarFeature", feature),
        "App::PropertyString",
        "AvatarType",
        "Avatar",
    )
    new_document = _application_new_document(
        cast("_FreeCADApplication", application),
        "ClothSewing",
    )

    assert created is feature and found is feature and new_document is document, (
        "FreeCAD adapter helpers must return the objects exposed by the runtime API"
    )
    assert document.addObject.call_args.args == ("Mesh::Feature", "ClothAvatar"), (
        "Object creation must preserve the FreeCAD type and name arguments"
    )
    assert document.getObject.call_args.args == ("DrapeTarget",), (
        "Object lookup must preserve the requested internal document name"
    )
    assert feature.addProperty.call_args.args == ("App::PropertyString", "AvatarType", "Avatar"), (
        "Property creation must preserve the FreeCAD property contract"
    )
    assert application.newDocument.call_args.args == ("ClothSewing",), (
        "Document creation must preserve the requested internal name"
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
    assert pose_data == {
        "preset": "standing",
        "left_arm_angle": LEGACY_ARM_ANGLE,
        "right_arm_angle": LEGACY_ARM_ANGLE,
    }, "Schema-one payloads must expose their serialized pose mapping"

    angles = {
        "left_arm_angle": LEGACY_ARM_ANGLE,
        "right_arm_angle": LEGACY_ARM_ANGLE,
    }
    _migrate_legacy_pose_angles(payload, "standing", angles)
    assert angles == {
        "left_arm_angle": STANDING_ARM_ANGLE,
        "right_arm_angle": STANDING_ARM_ANGLE,
    }, "Legacy sentinel angles must migrate to the standing preset defaults"

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
    assert _legacy_pose_data(newer_payload) is None, (
        "Current-schema payloads must not be treated as legacy migration inputs"
    )


def test_legacy_avatar_command_dotted_import_resolves_to_current_module() -> None:
    """Keep legacy dotted imports working after the lowercase source-file rename."""
    legacy_commands = import_module("freecad_cloth.avatar.AvatarCommands")
    assert legacy_commands.create_avatar is _avatar_commands.create_avatar, (
        "The legacy module path must resolve to the canonical avatar command implementation"
    )

# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral tests for the canonical avatar-provider contract."""

from types import SimpleNamespace

import pytest

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.AvatarProvider import (
    BUILTIN_AVATAR_PROVIDER_CLASSES,
    PROVIDER_IDS,
    AvatarProviderInfo,
    FreeCADGeometryAvatarProvider,
    ParametricAvatarProvider,
    provider_from_target,
)
from freecad_cloth.shared.Collision import CollisionSurface


class _Shape:
    """Minimal FreeCAD-like body exposing one triangular tessellation."""

    Name = "Body"
    Label = "Imported Body"

    def __init__(self) -> None:
        """Expose this fixture as its own Shape object."""
        self.Shape = self

    def isNull(self) -> bool:
        """Report a valid non-null shape."""
        return False

    def hashCode(self) -> int:
        """Return a deterministic test identity."""
        return 42

    def tessellate(
        self, _deflection: float
    ) -> tuple[tuple[SimpleNamespace, ...], tuple[tuple[int, int, int], ...]]:
        """Return a single triangle with finite coordinates."""
        vertices = tuple(
            SimpleNamespace(x=x, y=y, z=z)
            for x, y, z in ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0))
        )
        return vertices, ((0, 1, 2),)


def test_persisted_provider_ids_are_generated_from_registered_provider_metadata() -> None:
    """Keep the FreeCAD selector synchronized with the built-in provider registry."""
    expected = tuple(provider.info.provider_id for provider in BUILTIN_AVATAR_PROVIDER_CLASSES)
    assert PROVIDER_IDS == expected
    assert len(PROVIDER_IDS) == len(set(PROVIDER_IDS))


def test_parametric_provider_is_makehuman_mesh_provider() -> None:
    """Verify the parametric provider supplies the MakeHuman surface and collision mesh."""
    provider = ParametricAvatarProvider(AvatarParameters())
    assert provider.info == AvatarProviderInfo(
        "makehuman-hm08", "MakeHuman HM08 humanoid mesh", "high"
    )
    collision = provider.collision_surface()
    assert isinstance(collision, CollisionSurface)
    assert (collision.vertices, collision.triangles) == provider.surface()
    assert len(provider.landmarks()) > 5


def test_parametric_provider_keeps_authoritative_parameters() -> None:
    """Preserve the canonical parameters supplied to the parametric provider."""
    parameters = AvatarParameters()
    provider = ParametricAvatarProvider(parameters)
    assert provider.parameters() == parameters


def test_factory_selects_makehuman_provider() -> None:
    """Select the parametric provider for a mannequin target."""
    provider = provider_from_target(None, "Mannequin", AvatarParameters())
    assert isinstance(provider, ParametricAvatarProvider)


def test_factory_selects_freecad_provider() -> None:
    """Select imported geometry and validate its neutral collision surface."""
    source = _Shape()
    provider = FreeCADGeometryAvatarProvider(source)
    assert provider.info.provider_id == "freecad-geometry"
    assert provider.source is source
    assert provider.parameters() is None
    collision = provider.collision_surface()
    assert isinstance(collision, CollisionSurface)
    assert (collision.vertices, collision.triangles) == provider.surface()


def test_freecad_provider_rejects_invalid_tessellation() -> None:
    """Reject non-finite and non-positive FreeCAD tessellation settings."""
    source = _Shape()
    for deflection in (0.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            FreeCADGeometryAvatarProvider(source, deflection)
    for thickness in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            FreeCADGeometryAvatarProvider(source, 1.0, thickness)


def test_factory_rejects_unknown_provider() -> None:
    """Reject target kinds that have no registered provider implementation."""
    with pytest.raises(ValueError, match="unsupported avatar provider target type"):
        provider_from_target(None, "Blender")

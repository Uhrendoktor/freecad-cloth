# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression coverage for quality/material/collision rebuild signatures."""

from itertools import pairwise
from types import SimpleNamespace

import pytest

from freecad_cloth.simulation.SimulationQualityRuntime import QualitySimulationProxy
from tests.support.assertions import require


def _scene() -> SimpleNamespace:
    """Create a valid, headless simulation scene with default quality controls.

    Returns:
        Mutable scene double containing all authored properties used by the proxy.
    """
    return SimpleNamespace(
        QualityPreset="Balanced",
        ParticleDistance=4.0,
        SolverIterations=8,
        SolverSubsteps=1,
        PinMode="Automatic",
        FabricDensity=150.0,
        FabricThickness=0.5,
        FabricStretch=0.02,
        FabricShear=0.02,
        FabricBend=0.01,
        FabricFriction=0.5,
        FabricColor=(0.72, 0.34, 0.46),
        FabricSpecular=0.25,
        FabricRoughness=0.65,
        FabricTransparency=0,
        AvatarSkinOffset=0.0,
        ClothPieces=(),
        Document=SimpleNamespace(Objects=()),
        Steps=0,
    )


def _execution_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[QualitySimulationProxy, SimpleNamespace, list[object]]:
    """Create a proxy fixture that records rebuilds requested by public execute calls.

    Args:
        monkeypatch: Fixture used to replace expensive solver operations with recorders.

    Returns:
        The quality proxy, its valid scene double, and the sequence of rebuilt signatures.
    """
    scene = _scene()
    proxy = QualitySimulationProxy()
    base = SimpleNamespace(
        backend=object(),
        source_signature=None,
        last_steps=0,
        seam_stitch_pairs={},
    )
    rebuilt_signatures: list[object] = []

    monkeypatch.setattr(proxy, "_base_or_restore", lambda: base)

    def build_demo(_scene: object, signature: object) -> None:
        """Record a derived-scene rebuild and retain its new source signature.

        Args:
            _scene: Simulation scene requested by the public execute lifecycle.
            signature: Normalized source and quality controls used to build that scene.
        """
        rebuilt_signatures.append(signature)
        base.source_signature = signature

    monkeypatch.setattr(proxy, "_build_demo", build_demo)
    monkeypatch.setattr(proxy, "_sync_seam_stitch_provenance", lambda _base: None)
    monkeypatch.setattr(proxy, "_advance", lambda _scene, _base, _count: None)
    monkeypatch.setattr(proxy, "_publish_state", lambda _scene, _base: None)
    return proxy, scene, rebuilt_signatures


def test_signature_changes_for_every_derived_simulation_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rebuild the derived scene after each authored quality or collision control changes.

    Args:
        monkeypatch: Fixture that replaces backend construction and publication operations.
    """
    proxy, scene, rebuilt_signatures = _execution_probe(monkeypatch)
    proxy.execute(scene)

    controls = (
        ("QualityPreset", "Final"),
        ("ParticleDistance", 2.0),
        ("SolverIterations", 16),
        ("SolverSubsteps", 2),
        ("FabricDensity", 300.0),
        ("FabricThickness", 0.8),
        ("FabricStretch", 0.04),
        ("FabricShear", 0.04),
        ("FabricBend", 0.02),
        ("FabricFriction", 0.8),
        ("AvatarSkinOffset", 3.0),
    )
    for name, value in controls:
        setattr(scene, name, value)
        proxy.execute(scene)

    require(
        condition=len(rebuilt_signatures) == len(controls) + 1,
        message=(
            "The public execute lifecycle must rebuild once initially and after every "
            "derived simulation control change."
        ),
    )
    require(
        condition=all(
            current != previous
            for previous, current in pairwise(rebuilt_signatures)
        ),
        message="Each authored control change must produce a distinct rebuild signature.",
    )


def test_identical_quality_signature_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid rebuilding the scene when the public execute inputs remain unchanged.

    Args:
        monkeypatch: Fixture that replaces backend construction and publication operations.
    """
    proxy, scene, rebuilt_signatures = _execution_probe(monkeypatch)

    proxy.execute(scene)
    proxy.execute(scene)

    require(
        condition=len(rebuilt_signatures) == 1,
        message="Repeated execution with unchanged controls must reuse the existing scene.",
    )

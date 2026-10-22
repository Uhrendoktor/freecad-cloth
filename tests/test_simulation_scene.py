# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for simulation pin semantics, rebuild signatures and seam provenance."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import freecad_cloth.simulation.SimulationObjects as simulation_objects
from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR, PieceIR, SeamIR
from freecad_cloth.simulation.SimulationObjects import resolve_pin_indices
from tests.support.assertions import require

if TYPE_CHECKING:
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
        PositionBasedDynamicsBackend,
    )

_EXPECTED_SEAM_SAMPLE_COUNT = 3
_EXPECTED_PIN_INDEX_COUNT = 2


def _simulation_signature() -> Callable[[object, list[object]], object]:
    """Return the private source-signature function for contract testing.

    Returns:
        A callable that computes the scene's rebuild signature.
    """
    return cast(
        Callable[[object, list[object]], object],
        getattr(simulation_objects, "_simulation_source_signature"),
    )


def test_pin_mode_semantics_preserve_automatic_defaults_and_support_no_pins() -> None:
    """Verify automatic, explicit and disabled pin modes resolve distinctly."""
    legacy = SimpleNamespace(PinSelection=[])
    automatic = SimpleNamespace(PinSelection=[], PinMode="Automatic")
    explicit = SimpleNamespace(PinSelection=["2", "5"], PinMode="Explicit")
    explicit_empty = SimpleNamespace(PinSelection=[], PinMode="Explicit")
    none = SimpleNamespace(PinSelection=["2", "5"], PinMode="None")

    require(
        condition=resolve_pin_indices(legacy, 8, (0, 7)) == (0, 7),
        message="Legacy scenes must retain their automatic pin defaults.",
    )
    require(
        condition=resolve_pin_indices(automatic, 8, (0, 7)) == (0, 7),
        message="Automatic pin mode must preserve the supplied defaults.",
    )
    require(
        condition=resolve_pin_indices(explicit, 8, (0, 7)) == (2, 5),
        message="Explicit pin mode must resolve the selected indices.",
    )
    require(
        condition=resolve_pin_indices(explicit_empty, 8, (0, 7)) == (),
        message="An empty explicit selection must produce no pinned indices.",
    )
    require(
        condition=resolve_pin_indices(none, 8, (0, 7)) == (),
        message="Disabled pin mode must ignore a stored pin selection.",
    )


def test_pin_mode_is_part_of_rebuild_signature_and_none_ignores_pin_selection() -> None:
    """Verify rebuild signatures track pin modes but ignore disabled selections."""
    source = SimpleNamespace(
        Name="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(
                Angle=0.0,
                Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0),
            ),
        ),
    )
    target = SimpleNamespace(
        SourceObject=source,
        CollisionDeflection=1.0,
        CollisionThickness=0.0,
    )
    base = {"DrapeTarget": target, "StitchSamples": 8, "Document": SimpleNamespace(Objects=[])}
    automatic = SimpleNamespace(**base, PinMode="Automatic", PinSelection=[])
    explicit = SimpleNamespace(**base, PinMode="Explicit", PinSelection=["1", "2"])
    none_a = SimpleNamespace(**base, PinMode="None", PinSelection=["1", "2"])
    none_b = SimpleNamespace(**base, PinMode="None", PinSelection=["6", "7"])
    source_signature = _simulation_signature()

    require(
        condition=source_signature(automatic, []) != source_signature(explicit, []),
        message="Changing automatic to explicit pins must change the rebuild signature.",
    )
    require(
        condition=source_signature(explicit, []) != source_signature(none_a, []),
        message="Changing the pin mode to None must change the rebuild signature.",
    )
    require(
        condition=source_signature(none_a, []) == source_signature(none_b, []),
        message="Pin selections must not affect rebuild signatures when pin mode is None.",
    )


def test_pin_selection_is_part_of_rebuild_signature() -> None:
    """Verify a changed explicit pin selection invalidates the rebuild signature."""
    source = SimpleNamespace(
        Name="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
        ),
    )
    target = SimpleNamespace(SourceObject=source, CollisionDeflection=1.0, CollisionThickness=0.0)
    scene_a = SimpleNamespace(
        DrapeTarget=target,
        PinSelection=["1", "2"],
        StitchSamples=8,
        Document=SimpleNamespace(Objects=[]),
    )
    scene_b = SimpleNamespace(
        DrapeTarget=target,
        PinSelection=["3", "4"],
        StitchSamples=8,
        Document=SimpleNamespace(Objects=[]),
    )
    source_signature = _simulation_signature()

    require(
        condition=source_signature(scene_a, []) != source_signature(scene_b, []),
        message="Changing an explicit pin selection must change the rebuild signature.",
    )


def test_seam_pair_records_preserve_exact_solver_stitch_provenance() -> None:
    """Verify solver stitch pairs preserve authored seam direction and identity."""
    pattern = PatternIR(
        (
            PieceIR(
                "piece-a",
                "PieceA",
                (BoundaryIR("piece-a:edge:0", "line", ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0))),),
            ),
            PieceIR(
                "piece-b",
                "PieceB",
                (BoundaryIR("piece-b:edge:0", "line", ((0.0, 100.0, 0.0), (20.0, 100.0, 0.0))),),
            ),
        ),
        (
            SeamIR(
                id="seam-1",
                piece_a="piece-a",
                edge_a="piece-a:edge:0",
                piece_b="piece-b",
                edge_b="piece-b:edge:0",
                reversed_b=True,
            ),
        ),
    )
    panel_data = {
        "piece-a": {
            "boundary_edges": ((0, 1, 2),),
            "positions": (
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
            ),
        },
        "piece-b": {
            "boundary_edges": ((3, 4, 5),),
            "positions": (
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
                (0.0, 100.0, 0.0),
                (10.0, 100.0, 0.0),
                (20.0, 100.0, 0.0),
            ),
        },
    }
    seam_pair_records = cast(
        Callable[[PatternIR, dict[str, object]], tuple[object, object]],
        getattr(simulation_objects, "_seam_pair_records"),
    )
    pairs, records = seam_pair_records(
        pattern,
        panel_data,
        seam_samples=_EXPECTED_SEAM_SAMPLE_COUNT,
    )

    require(
        condition=pairs == ((0, 5), (1, 4), (2, 3)),
        message="Reversed seam stitching must preserve the authored pair order.",
    )
    require(
        condition=records == (("seam-1", "PieceA", "PieceB", ((0, 5), (1, 4), (2, 3))),),
        message="Seam records must preserve the seam ID and both piece names.",
    )


def test_simulation_proxy_does_not_mix_surface_and_legacy_sphere_collision() -> None:
    """Verify the simulation proxy forwards only the authoritative surface control."""
    class FakeBackend:
        """Capture calls made by the simulation proxy without solving particles."""

        def __init__(self) -> None:
            """Initialize an empty backend-call record."""
            self.calls: list[tuple[float, int, tuple[float, float, float], object]] = []

        def step(
            self,
            dt: float,
            iterations: int,
            gravity: tuple[float, float, float],
            surface: object,
        ) -> None:
            """Record one proxy simulation step.

            Args:
                dt: Time increment requested by the proxy.
                iterations: Solver iteration count requested by the proxy.
                gravity: Gravity vector passed to the backend.
                surface: Authoritative collision surface passed to the backend.
            """
            self.calls.append((dt, iterations, gravity, surface))

        def positions(self) -> tuple[tuple[float, float, float], ...]:
            """Return no positions for the recording-only backend.

            Returns:
                An empty particle-position sequence.
            """
            return ()

        @property
        def time(self) -> float:
            """Return the fake backend's current elapsed time.

            Returns:
                Zero because this backend does not advance a simulation.
            """
            return 0.0

        def finite(self) -> bool:
            """Report that the fake backend has only finite state.

            Returns:
                True because the test double stores no numerical solver state.
            """
            return True

    scene = SimpleNamespace(
        ClothPieces=[],
        Document=SimpleNamespace(Objects=[]),
        DrapeTarget=None,
        PinSelection=[],
        StitchSamples=8,
        Steps=1,
        TimeStep=1.0 / 60.0,
        Iterations=8,
        GravityX=0.0,
        GravityY=0.0,
        GravityZ=-9810.0,
        CollisionX=0.0,
        CollisionY=0.0,
        CollisionZ=0.0,
        CollisionRadius=38.0,
        DrapePanels=[],
    )
    proxy = simulation_objects.SimulationProxy()
    proxy.backend = cast("PositionBasedDynamicsBackend", FakeBackend())
    proxy.collision_surface = object()
    proxy.source_signature = _simulation_signature()(scene, [])
    proxy.execute(scene)

    require(
        condition=proxy.backend.calls
        == [
            (
                scene.TimeStep,
                scene.Iterations,
                (scene.GravityX, scene.GravityY, scene.GravityZ),
                proxy.collision_surface,
            )
        ],
        message="The proxy must pass the collision surface without activating legacy sphere controls.",
    )

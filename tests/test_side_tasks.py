# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for pattern export, collision and sewing edge adapters."""

from collections.abc import Callable, Sequence
from importlib import import_module
from types import SimpleNamespace
from typing import Protocol, cast

import pytest

from fixtures.garment_fixtures import mirrored_pair, multi_piece, two_piece_rectangle
from freecad_cloth.pattern.PatternDerivedGeometry import (
    Notch,
    PatternMark,
    add_marks,
    add_notches,
    derive_cut_boundary,
)
from freecad_cloth.pattern.PatternExport import from_dxf_metadata, to_dxf, to_svg
from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.simulation.DrapeVisualSanity import assert_drape_diagnostics
from freecad_cloth.shared.collision import CollisionSurface
from tests.support.assertions import require

_SEWING_OBJECTS = import_module("freecad_cloth.sewing.SewingObjects")
_EDGE_LENGTH_ATTRIBUTE = "_edge_length"
_EDGE_POINTS_ATTRIBUTE = "_edge_points"
_edge_length = cast(
    "Callable[[object, int], float]", getattr(_SEWING_OBJECTS, _EDGE_LENGTH_ATTRIBUTE)
)
_edge_points = cast(
    "Callable[..., tuple[object, object]]", getattr(_SEWING_OBJECTS, _EDGE_POINTS_ATTRIBUTE)
)

SAMPLE_PATTERN_WIDTH_MM = 100
SAMPLE_PATTERN_HEIGHT_MM = 50
EXPECTED_SEAM_COUNT = 3
EXPECTED_EDGE_LENGTH_MM = 5.0
EXPECTED_START_POINT = (10.0, -1.0, 2.2)
EXPECTED_END_POINT = (7.0, -1.0, 2.2)
EXPECTED_COLLISION_CENTER = (1 / 3, 1 / 3, 0.0)


class _VectorLike(Protocol):
    """Coordinates exposed by the FreeCAD vector stand-in."""

    x: float
    y: float
    z: float


class _SampledPatternPiece(Protocol):
    """Outline API consumed by deterministic garment-fixture assertions."""

    def sampled_outline(self) -> object:
        """Return the piece's ordered outline samples.

        Returns:
            The sampled outline in the piece's local coordinate system.
        """
        ...


class _Vector:
    """Minimal mutable vector used to verify piece-placement transforms."""

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        """Create a vector with explicit coordinates.

        Args:
            x: Horizontal coordinate in millimetres.
            y: Vertical coordinate in millimetres.
            z: Depth coordinate in millimetres.
        """
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


def _transform_vector(value: _VectorLike) -> _Vector:
    """Apply the fixed rotation and translation used by the edge regression.

    Args:
        value: Local coordinate vector before the placement transform.

    Returns:
        A new vector after the test transform is applied.
    """
    return _Vector(-value.y + 10.0, value.x - 5.0, value.z + 2.0)


def test_svg_units_and_stable_ids() -> None:
    """Preserve physical-unit labels and deterministic edge identifiers in SVG."""
    svg = to_svg(rectangle(SAMPLE_PATTERN_WIDTH_MM, SAMPLE_PATTERN_HEIGHT_MM))
    require(
        condition='data-units="mm"' in svg,
        message="SVG export must label the canonical millimetre units.",
    )
    require(
        condition='data-edge-ids="bottom right top left"' in svg,
        message="SVG export must preserve stable edge identifiers.",
    )
    require(
        condition=f'width="{SAMPLE_PATTERN_WIDTH_MM}mm"' in svg,
        message="SVG width must preserve the pattern's physical width.",
    )
    require(
        condition=f'height="{SAMPLE_PATTERN_HEIGHT_MM}mm"' in svg,
        message="SVG height must preserve the pattern's physical height.",
    )


def test_collision_surface_contract() -> None:
    """Validate the neutral collision surface and its geometric centroid."""
    surface = CollisionSurface(
        ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        ((0, 1, 2),),
        thickness=1.0,
    )
    surface.validate()
    require(
        condition=surface.center == EXPECTED_COLLISION_CENTER,
        message="Collision-surface center must equal the triangle centroid.",
    )


def test_golden_fixtures_are_deterministic() -> None:
    """Keep representative multi-piece fixtures stable between constructions."""
    first_fixture = cast("dict[str, object]", two_piece_rectangle())
    second_fixture = cast("dict[str, object]", two_piece_rectangle())
    first_pieces = cast("Sequence[_SampledPatternPiece]", first_fixture["pieces"])
    second_pieces = cast("Sequence[_SampledPatternPiece]", second_fixture["pieces"])
    first_outline = first_pieces[0].sampled_outline()
    second_outline = second_pieces[0].sampled_outline()
    require(
        condition=first_outline == second_outline,
        message="Repeated pattern-fixture construction must produce the same outline.",
    )
    require(
        condition=mirrored_pair()["mirrored"] is True,
        message="The mirrored fixture must retain its mirror contract.",
    )
    require(
        condition=multi_piece()["seams"] == EXPECTED_SEAM_COUNT,
        message="The multi-piece fixture must preserve its expected seam count.",
    )


def test_pattern_construction_and_dxf_export() -> None:
    """Keep derived cutting geometry and DXF layer metadata deterministic."""
    pattern = rectangle(SAMPLE_PATTERN_WIDTH_MM, 60)
    derived = add_notches(derive_cut_boundary(pattern, 5), [Notch("waist", "right", 0.5)])
    derived = add_marks(
        derived, [PatternMark("grain", "Grainline", angle=90, length=40, text="Grain")]
    )
    svg = to_svg(pattern, derived=derived)
    require(
        condition='id="sewing-boundary"' in svg,
        message="SVG export must include the sewing boundary.",
    )
    require(
        condition='id="cut-boundary"' in svg,
        message="SVG export must include the derived cut boundary.",
    )
    require(
        condition='data-notch-ids="waist"' in svg,
        message="SVG export must retain the semantic notch identifier.",
    )
    require(
        condition='data-kind="Grainline"' in svg,
        message="SVG export must identify grainline annotations.",
    )
    dxf = to_dxf(pattern, derived=derived)
    require(
        condition="LWPOLYLINE" in dxf,
        message="DXF export must encode pattern boundaries as polylines.",
    )
    require(
        condition="8\nSEWING" in dxf,
        message="DXF export must retain the sewing layer.",
    )
    require(
        condition="8\nCUT" in dxf,
        message="DXF export must retain the cut layer.",
    )
    require(
        condition=from_dxf_metadata(dxf)
        == {
            "version": 1,
            "units": "mm",
            "edge_ids": ["bottom", "right", "top", "left"],
        },
        message="DXF export must round-trip canonical unit and edge metadata.",
    )


def test_invalid_pattern_mark_reference_is_rejected() -> None:
    """Reject a pattern mark that names a nonexistent segment."""
    with pytest.raises(ValueError, match="pattern mark references unknown segment"):
        add_marks(
            derive_cut_boundary(rectangle(10, 10), 1),
            [PatternMark("bad", "Fold", segment_id="missing")],
        )


def test_closed_sewing_outline_edge_wraps_to_first_vertex() -> None:
    """Measure the closing edge back to the first vertex of the outline."""
    piece = SimpleNamespace(
        Width=999.0,
        Height=999.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 3)]),
    )
    require(
        condition=_edge_length(piece, 2) == EXPECTED_EDGE_LENGTH_MM,
        message="The last outline edge must wrap to the first vertex.",
    )


def test_sewing_edge_points_apply_rotated_piece_placement_once() -> None:
    """Apply a rotated piece placement exactly once to the requested seam edge."""
    piece = SimpleNamespace(
        Width=4.0,
        Height=3.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 3)]),
        Placement=SimpleNamespace(multVec=_transform_vector),
    )
    raw_start, raw_end = _edge_points(
        piece,
        1,
        0.0,
        1.0,
        z=0.2,
        vector_factory=_Vector,
    )
    start = cast("_Vector", raw_start)
    end = cast("_Vector", raw_end)
    require(
        condition=(start.x, start.y, start.z) == EXPECTED_START_POINT,
        message="The transformed seam start must match the placed local coordinate.",
    )
    require(
        condition=(end.x, end.y, end.z) == EXPECTED_END_POINT,
        message="The transformed seam end must match the placed local coordinate.",
    )


def test_drape_visual_diagnostics_accept_clean_result() -> None:
    """Accept a structurally plausible drape without fatal diagnostics."""
    assert_drape_diagnostics(
        (
            {
                "panel": "Front",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": [],
            },
        )
    )


def test_drape_visual_diagnostics_allows_only_explicit_exception() -> None:
    """Allow a fatal diagnostic only when the audit names that exact exception."""
    assert_drape_diagnostics(
        (
            {
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": ["below-hem-candidate"],
            },
        ),
        allowed_diagnostics={"below-hem-candidate"},
    )


def test_drape_visual_diagnostics_reject_detached_collapsed_or_below_hem() -> None:
    """Fail the visual audit closed for detached, collapsed, or below-hem outputs."""
    cases = (
        {"failure_classification": {"state": "detached-candidate"}, "diagnostics": []},
        {
            "failure_classification": {"state": "structurally-plausible"},
            "diagnostics": ["collapsed-candidate"],
        },
        {
            "failure_classification": {"state": "structurally-plausible"},
            "diagnostics": ["below-hem-candidate"],
        },
        {
            "failure_classification": {"state": "structurally-plausible"},
            "diagnostics": ["lateral-detached-candidate"],
        },
    )
    for record in cases:
        with pytest.raises(RuntimeError, match="drape visual acceptance failed closed"):
            assert_drape_diagnostics((record,))


if __name__ == "__main__":
    manual_tests: tuple[Callable[[], None], ...] = (
        test_svg_units_and_stable_ids,
        test_collision_surface_contract,
        test_golden_fixtures_are_deterministic,
        test_pattern_construction_and_dxf_export,
        test_invalid_pattern_mark_reference_is_rejected,
        test_closed_sewing_outline_edge_wraps_to_first_vertex,
        test_sewing_edge_points_apply_rotated_piece_placement_once,
        test_drape_visual_diagnostics_accept_clean_result,
        test_drape_visual_diagnostics_allows_only_explicit_exception,
        test_drape_visual_diagnostics_reject_detached_collapsed_or_below_hem,
    )
    for manual_test in manual_tests:
        manual_test()

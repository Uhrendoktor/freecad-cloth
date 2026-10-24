# Copyright (C) 2026 FreeCAD Cloth contributors
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixtures.garment_fixtures import mirrored_pair, multi_piece, two_piece_rectangle
from freecad_cloth.avatar.AvatarCollision import (
    AvatarSpec,
    CollisionSurface,
)
from freecad_cloth.pattern.PatternDerivedGeometry import (
    Notch,
    PatternMark,
    add_marks,
    add_notches,
    derive_cut_boundary,
)
from freecad_cloth.pattern.PatternExport import from_dxf_metadata, to_dxf, to_svg
from freecad_cloth.pattern.PatternGeometry import (
    rectangle,
)
from freecad_cloth.sewing.SewingObjects import _edge_length, _edge_points
from freecad_cloth.simulation.DrapeVisualSanity import assert_drape_diagnostics


def test_svg_units_and_stable_ids():
    svg = to_svg(rectangle(100, 50))
    assert 'data-units="mm"' in svg
    assert 'data-edge-ids="bottom right top left"' in svg
    assert 'width="100mm"' in svg
    assert 'height="50mm"' in svg


def test_avatar_contract():
    surface = CollisionSurface(((0, 0, 0), (1, 0, 0), (0, 1, 0)), ((0, 1, 2),), thickness=1.0)
    avatar = AvatarSpec("fixture", collision=surface)
    avatar.validate()
    assert surface.center == (1 / 3, 1 / 3, 0.0)


def test_golden_fixtures_are_deterministic():
    assert (
        two_piece_rectangle()["pieces"][0].sampled_outline()
        == two_piece_rectangle()["pieces"][0].sampled_outline()
    )
    assert mirrored_pair()["mirrored"] is True
    assert multi_piece()["seams"] == 3


def test_pattern_construction_and_dxf_export():
    pattern = rectangle(100, 60)
    derived = add_notches(derive_cut_boundary(pattern, 5), [Notch("waist", "right", 0.5)])
    derived = add_marks(
        derived, [PatternMark("grain", "Grainline", angle=90, length=40, text="Grain")]
    )
    svg = to_svg(pattern, derived=derived)
    assert 'id="sewing-boundary"' in svg
    assert 'id="cut-boundary"' in svg
    assert 'data-notch-ids="waist"' in svg
    assert 'data-kind="Grainline"' in svg
    dxf = to_dxf(pattern, derived=derived)
    assert "LWPOLYLINE" in dxf
    assert "8\nSEWING" in dxf
    assert "8\nCUT" in dxf
    assert from_dxf_metadata(dxf) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "top", "left"],
    }


def test_invalid_pattern_mark_reference_is_rejected():
    try:
        add_marks(
            derive_cut_boundary(rectangle(10, 10), 1),
            [PatternMark("bad", "Fold", segment_id="missing")],
        )
        raise AssertionError
    except ValueError:
        pass


def test_closed_sewing_outline_edge_wraps_to_first_vertex():
    piece = SimpleNamespace(Width=999.0, Height=999.0, SewingOutline=repr([(0, 0), (4, 0), (4, 3)]))
    assert _edge_length(piece, 2) == 5.0


def test_sewing_edge_points_apply_rotated_piece_placement_once():
    class Vector:
        def __init__(self, x, y, z=0.0):
            self.x, self.y, self.z = float(x), float(y), float(z)

    class RotatedPlacement:
        def multVec(self, value):
            return Vector(-value.y + 10, value.x - 5, value.z + 2)

    FakeApp = type("FakeApp", (), {"Vector": Vector})

    piece = SimpleNamespace(
        Width=4.0,
        Height=3.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 3)]),
        Placement=RotatedPlacement(),
    )
    start, end = _edge_points(piece, 1, 0.0, 1.0, z=0.2, vector_factory=FakeApp().Vector)
    assert (start.x, start.y, start.z) == (10.0, -1.0, 2.2)
    assert (end.x, end.y, end.z) == (7.0, -1.0, 2.2)


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("side-task tests passed")


def test_drape_visual_diagnostics_accept_clean_result():
    assert_drape_diagnostics(
        (
            {
                "panel": "Front",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": [],
            },
        )
    )


def test_drape_visual_diagnostics_allows_only_explicit_exception():
    assert_drape_diagnostics(
        (
            {
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": ["below-hem-candidate"],
            },
        ),
        allowed_diagnostics={"below-hem-candidate"},
    )


def test_drape_visual_diagnostics_reject_detached_collapsed_or_below_hem():
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
        try:
            assert_drape_diagnostics((record,))
        except RuntimeError as exc:
            assert "drape visual acceptance failed closed" in str(exc)
        else:
            msg = "fatal drape diagnostics were accepted"
            raise AssertionError(msg)
